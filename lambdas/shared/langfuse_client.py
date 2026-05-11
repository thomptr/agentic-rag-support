"""Langfuse SDK init + child-span helper for executor-tool Lambdas.

The Lambda runtime keeps the Python interpreter warm across invocations, so the
heavy SDK init happens once at module import. Credentials are read from
Secrets Manager — the ARNs are passed via env vars set by the Lambda's
OpenTofu module (`LANGFUSE_SECRET_REF` + `LANGFUSE_PUBLIC_REF`).

Per contracts/tool-lambda.md, redaction is mandatory before any payload is
written to a span. The `REDACT_KEYS` set is the canonical list — tests under
`lambdas/shared/tests/test_redact.py` lock it.
"""

from __future__ import annotations

import json
import os
from typing import Any

import boto3

from lambdas.shared.tracing import TraceMeta

# Langfuse ships in the Lambda Layer at runtime; in unit-test environments the
# package may not be installed. Import lazily so the module is still importable
# either way — span creation no-ops cleanly when the SDK is absent.
try:
    from langfuse import Langfuse  # type: ignore[import-not-found]
except ImportError:
    Langfuse = None  # type: ignore[assignment, misc]

REDACT_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "card_number",
        "cvv",
        "secret",
        "client_secret",
        "authorization",
    }
)
REDACTION_PLACEHOLDER = "[REDACTED]"


def _read_secret_string(secret_arn: str, *, region: str | None = None) -> str:
    """Fetch a Secrets Manager string. Raises if the secret is binary or missing."""
    client = boto3.client("secretsmanager", region_name=region or os.environ.get("AWS_REGION"))
    resp = client.get_secret_value(SecretId=secret_arn)
    if "SecretString" not in resp:
        raise RuntimeError(f"Secret {secret_arn} has no SecretString")
    return resp["SecretString"]


def _parse_secret_field(raw: str, field: str) -> str:
    """Secrets are stored as JSON objects (e.g. {\"LANGFUSE_SECRET_KEY\": \"sk-...\"}). Extract one field."""
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or field not in parsed:
        raise RuntimeError(f"Secret JSON missing required field {field!r}")
    return parsed[field]


def _init_langfuse():
    """Initialize the Langfuse client at cold start, or return None if config absent.

    A missing secret ARN or fetch failure is intentionally non-fatal: the Lambda
    still serves traffic, and the failure is visible in CloudWatch logs. This
    avoids one bad rotation taking down the executor.
    """
    if Langfuse is None:
        # Package not installed in this environment (e.g. unit tests).
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
        return Langfuse(secret_key=secret_key, public_key=public_key, host=host)
    except Exception as exc:  # noqa: BLE001 — surface fault, keep handler alive
        print(f"LANGFUSE_INIT_FAILED: {exc!r}")
        return None


_LANGFUSE = _init_langfuse()


def redact(payload: Any) -> Any:
    """Recursively replace values whose keys match REDACT_KEYS (case-insensitive)."""
    if isinstance(payload, dict):
        return {
            k: REDACTION_PLACEHOLDER if k.lower() in REDACT_KEYS else redact(v)
            for k, v in payload.items()
        }
    if isinstance(payload, list):
        return [redact(item) for item in payload]
    return payload


def create_child_span(
    *,
    name: str,
    trace_meta: TraceMeta,
    input_payload: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> Any:
    """Open a Langfuse child span linked to the agent's parent trace.

    Returns the span object so the handler can later set `output` + `end()`.
    Returns None if the SDK isn't initialized — handlers should treat the return
    value as a context-manager-ish optional and tolerate None.
    """
    if _LANGFUSE is None:
        return None
    return _LANGFUSE.span(
        name=name,
        trace_id=trace_meta.trace_id,
        parent_observation_id=trace_meta.parent_span_id,
        input=redact(input_payload),
        metadata=metadata or {},
    )


def flush() -> None:
    """Flush queued spans before the Lambda runtime freezes the process."""
    if _LANGFUSE is None:
        return
    try:
        _LANGFUSE.flush()
    except Exception as exc:  # noqa: BLE001
        print(f"LANGFUSE_FLUSH_FAILED: {exc!r}")
