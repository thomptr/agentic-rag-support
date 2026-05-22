"""Langfuse client + trace context helpers for the agent runtime.

Mirrors the pattern used by `lambdas/shared/langfuse_client.py`: the SDK is
initialized once at cold start from Secrets Manager (ARNs passed via env vars
by the AgentCore module), and is intentionally tolerant of missing credentials
so a misconfig doesn't take down the runtime.

The agent emits a single parent trace per invocation; LLM calls, graph nodes,
and tool dispatches become child spans of that trace via the `span()` context
manager. `current_trace_meta()` returns the dict the `gateway_executor` passes
to Lambdas so their child spans link to the same trace.
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

# Best-effort `.env` load so local-mode entry points (Streamlit, the FastAPI
# `/query` server, ad-hoc scripts) see LANGFUSE_* env vars without each one
# having to remember to call `load_dotenv()` themselves. `override=False` means
# cloud-mode envs (set by AgentCore Runtime / ECS task definitions) win — this
# is purely a local-dev convenience that the cloud path never sees.
#
# Skipped when running under pytest so test fixtures retain full control over
# which LANGFUSE_* vars are visible — auto-loading `.env` during tests would
# silently inject real credentials and break monkeypatch-based init scenarios.
# We use `"pytest" in sys.modules` (set from pytest startup) rather than
# `PYTEST_CURRENT_TEST` (only set during the test phase, not collection — and
# this module gets imported during collection).
if "pytest" not in sys.modules:
    try:
        from dotenv import load_dotenv as _load_dotenv

        _load_dotenv(override=False)
    except ImportError:
        pass

# v2 SDK — wire format matches lambdas/shared/langfuse_client.py (Lambdas pin
# 2.x; the agent must match so parent_observation_id values are compatible).
try:
    from langfuse import Langfuse  # type: ignore[import-not-found]
except ImportError:
    Langfuse = None  # type: ignore[assignment, misc]


def _read_secret_string(secret_arn: str, *, region: str | None = None) -> str:
    # Lazy import — boto3 is only needed at runtime when LANGFUSE_*_REF is
    # set, NOT at module import. Keeping it lazy means test environments and
    # local dev without boto3 installed can still import this module.
    import boto3

    client = boto3.client("secretsmanager", region_name=region or os.environ.get("AWS_REGION"))
    resp = client.get_secret_value(SecretId=secret_arn)
    if "SecretString" not in resp:
        raise RuntimeError(f"Secret {secret_arn} has no SecretString")
    return resp["SecretString"]


def _parse_secret_field(raw: str, field: str) -> str:
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or field not in parsed:
        raise RuntimeError(f"Secret JSON missing required field {field!r}")
    return parsed[field]


# Public init status — read by /health and the Streamlit sidebar so a misconfig
# surfaces in the UI instead of just CloudWatch. Updated once at cold start.
# Shape: {"state": "ok"|"disabled"|"failed", "source": "secrets_manager"|"env"|"",
#         "host": "...", "reason": "..." (only when state != "ok")}.
init_status: dict[str, str] = {
    "state": "disabled",
    "source": "",
    "host": "",
    "reason": "not_initialized",
}


def _init_langfuse():
    """Cold-start initialization. Returns a Langfuse client or None.

    Two credential sources are supported, checked in order:
      1. LANGFUSE_*_REF (Secrets Manager ARNs) — the cloud path; SDK creds are
         pulled from Secrets Manager so they're never baked into env vars.
      2. LANGFUSE_SECRET_KEY / LANGFUSE_PUBLIC_KEY (raw values) — the local
         dev path; lets a `.env` drive Langfuse without round-tripping through
         AWS. `LANGFUSE_BASE_URL` is accepted as an alias for `LANGFUSE_HOST`
         since that's the name the Langfuse dashboard hands you.

    `LANGFUSE_REQUIRED=true` makes init failures fatal — use it in CI and any
    environment where silently losing traces is unacceptable. The default
    behavior remains best-effort because we never want a bad rotation to take
    down the agent in production.
    """
    required = os.environ.get("LANGFUSE_REQUIRED", "").strip().lower() in {"1", "true", "yes"}

    def _fail(reason: str, *, exc: BaseException | None = None) -> None:
        msg = f"LANGFUSE_INIT_{('FAILED' if exc else 'SKIPPED')}: {reason}"
        if exc is not None:
            msg += f" ({exc!r})"
        print(msg)
        init_status["state"] = "failed" if exc else "disabled"
        init_status["reason"] = reason
        if required:
            raise RuntimeError(
                f"LANGFUSE_REQUIRED is set but init failed: {reason}"
                + (f" — {exc!r}" if exc else "")
            )

    if Langfuse is None:
        _fail("SDK not installed in this environment")
        return None
    secret_arn = os.environ.get("LANGFUSE_SECRET_REF", "").strip()
    public_arn = os.environ.get("LANGFUSE_PUBLIC_REF", "").strip()
    host = (
        os.environ.get("LANGFUSE_HOST", "").strip()
        or os.environ.get("LANGFUSE_BASE_URL", "").strip()
        or "https://cloud.langfuse.com"
    )
    init_status["host"] = host

    secret_key: str | None = None
    public_key: str | None = None
    source = ""

    if secret_arn and public_arn:
        source = "secrets_manager"
        try:
            secret_key = _parse_secret_field(_read_secret_string(secret_arn), "LANGFUSE_SECRET_KEY")
            public_key = _parse_secret_field(_read_secret_string(public_arn), "LANGFUSE_PUBLIC_KEY")
        except Exception as exc:  # noqa: BLE001
            _fail("secrets_manager fetch", exc=exc)
            return None
    else:
        raw_secret = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
        raw_public = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
        if raw_secret and raw_public:
            source = "env"
            secret_key = raw_secret
            public_key = raw_public

    if not secret_key or not public_key:
        _fail(
            "no credentials (set LANGFUSE_*_REF for cloud or "
            "LANGFUSE_SECRET_KEY/LANGFUSE_PUBLIC_KEY for local)"
        )
        return None

    try:
        client = Langfuse(secret_key=secret_key, public_key=public_key, host=host)
        print(f"LANGFUSE_INIT_OK: host={host} source={source}")
        init_status["state"] = "ok"
        init_status["source"] = source
        init_status["reason"] = ""
        return client
    except Exception as exc:  # noqa: BLE001
        _fail("Langfuse client construction", exc=exc)
        return None


_LANGFUSE = _init_langfuse()

# Tracks the current parent observation (a Langfuse Stateful*Client). Each
# `span(...)` swaps this for its own child for the duration of the block, then
# restores. `None` means "no active trace" — helpers no-op.
_current_parent: ContextVar[Any] = ContextVar("langfuse_current_parent", default=None)
_current_trace_id: ContextVar[str | None] = ContextVar("langfuse_current_trace_id", default=None)


def is_enabled() -> bool:
    return _LANGFUSE is not None


@contextmanager
def trace(
    *,
    name: str,
    input_payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
):
    """Open the parent trace for an invocation. Use once per agent call.

    Yields the trace handle (or None if Langfuse disabled). On exit the trace
    is ended and the SDK is flushed so the spans land before the AgentCore
    Runtime freezes the worker.
    """
    if _LANGFUSE is None:
        yield None
        return

    handle = _LANGFUSE.trace(
        name=name,
        input=input_payload or {},
        metadata=metadata or {},
        session_id=session_id,
        user_id=user_id,
    )
    parent_token = _current_parent.set(handle)
    trace_token = _current_trace_id.set(handle.id)
    try:
        yield handle
    finally:
        _current_parent.reset(parent_token)
        _current_trace_id.reset(trace_token)
        try:
            _LANGFUSE.flush()
        except Exception as exc:  # noqa: BLE001
            print(f"LANGFUSE_FLUSH_FAILED: {exc!r}")


@contextmanager
def span(
    *,
    name: str,
    input_payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
):
    """Open a child span under the current parent. No-op if no trace is active.

    Caller can set `output` on the yielded handle (or assign to its `.output`
    via a `.end(output=...)` call later — but this context manager already
    calls `.end()` on exit, so just attach output before exit).
    """
    parent = _current_parent.get()
    if _LANGFUSE is None or parent is None:
        yield _NullSpan()
        return

    child = parent.span(
        name=name,
        input=input_payload or {},
        metadata=metadata or {},
    )
    parent_token = _current_parent.set(child)
    try:
        yield child
    finally:
        _current_parent.reset(parent_token)
        try:
            child.end()
        except Exception as exc:  # noqa: BLE001
            print(f"LANGFUSE_SPAN_END_FAILED: {exc!r}")


@contextmanager
def generation(
    *,
    name: str,
    model: str,
    input_payload: Any | None = None,
    metadata: dict[str, Any] | None = None,
):
    """Open a Langfuse `generation` observation around an LLM call.

    Captures `model`, `input` (messages), `output` (completion), and
    `usage_details` if the caller sets them on the yielded handle before exit.
    Falls back to a no-op when Langfuse isn't initialized.
    """
    parent = _current_parent.get()
    if _LANGFUSE is None or parent is None:
        yield _NullSpan()
        return

    gen = parent.generation(
        name=name,
        model=model,
        input=input_payload,
        metadata=metadata or {},
    )
    parent_token = _current_parent.set(gen)
    try:
        yield gen
    finally:
        _current_parent.reset(parent_token)
        try:
            gen.end()
        except Exception as exc:  # noqa: BLE001
            print(f"LANGFUSE_GEN_END_FAILED: {exc!r}")


def current_trace_meta(*, session_id: str, run_id: str) -> dict[str, str]:
    """Build the trace_meta dict passed to Lambdas via the Gateway.

    Returns the canonical 4-field shape per `lambdas/shared/tracing.py`. If no
    trace is active, returns synthesized UUIDs so the Lambdas still get a
    schema-valid payload (their child spans will be orphans, but the call
    still succeeds — observability is best-effort).
    """
    import uuid as _uuid

    trace_id = _current_trace_id.get()
    parent = _current_parent.get()
    if trace_id is None or parent is None:
        return {
            "trace_id": str(_uuid.uuid4()),
            "parent_span_id": str(_uuid.uuid4()),
            "session_id": session_id,
            "run_id": run_id,
        }
    return {
        "trace_id": trace_id,
        "parent_span_id": parent.id,
        "session_id": session_id,
        "run_id": run_id,
    }


class _NullSpan:
    """Stand-in returned by `span()` when Langfuse is disabled. Supports the
    same `.end(output=...)` / attribute-assignment surface so callers don't
    need to None-check."""

    id = ""

    def end(self, **_kwargs: Any) -> None:
        return None

    def update(self, **_kwargs: Any) -> None:
        return None

    def __setattr__(self, _name: str, _value: Any) -> None:
        return None
