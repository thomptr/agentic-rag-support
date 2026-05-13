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
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

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


def _init_langfuse():
    """Cold-start initialization. Returns a Langfuse client or None.

    Missing credentials are non-fatal — the helpers below all no-op when the
    client is None, so the agent still serves traffic. The init outcome is
    printed once at cold start so a developer can grep CloudWatch for it.
    """
    if Langfuse is None:
        print("LANGFUSE_INIT_SKIPPED: SDK not installed in this environment")
        return None
    secret_arn = os.environ.get("LANGFUSE_SECRET_REF", "").strip()
    public_arn = os.environ.get("LANGFUSE_PUBLIC_REF", "").strip()
    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com").strip()
    if not secret_arn or not public_arn:
        print("LANGFUSE_INIT_SKIPPED: missing LANGFUSE_*_REF env vars")
        return None

    try:
        secret_key = _parse_secret_field(_read_secret_string(secret_arn), "LANGFUSE_SECRET_KEY")
        public_key = _parse_secret_field(_read_secret_string(public_arn), "LANGFUSE_PUBLIC_KEY")
        client = Langfuse(secret_key=secret_key, public_key=public_key, host=host)
        print(f"LANGFUSE_INIT_OK: host={host}")
        return client
    except Exception as exc:  # noqa: BLE001
        print(f"LANGFUSE_INIT_FAILED: {exc!r}")
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
