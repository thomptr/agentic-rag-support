"""Trace-context extraction for executor-tool Lambdas.

The agent-side `gateway_executor` propagates Langfuse trace continuity by
embedding `trace_meta` in the tool-call payload (see
specs/005-aws-agentcore-deployment/contracts/tool-lambda.md). Every Lambda
handler MUST validate that the field is present and well-formed before doing
real work, otherwise observability is silently broken.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

REQUIRED_TRACE_FIELDS = ("trace_id", "parent_span_id")


@dataclass(frozen=True)
class TraceMeta:
    trace_id: str
    parent_span_id: str
    session_id: str
    run_id: str


class MissingTraceContext(ValueError):
    """Raised when the incoming event lacks required trace_meta fields."""


def extract_trace_meta(event: dict[str, Any]) -> TraceMeta:
    """Return a populated TraceMeta or raise MissingTraceContext.

    Looks under `event["trace_meta"]` (top-level key in our contract). Any
    `KeyError`, missing-field, or empty-string condition surfaces as a single
    typed exception the handler converts to a 400 response.
    """

    meta = event.get("trace_meta")
    if not isinstance(meta, dict):
        raise MissingTraceContext("trace_meta is missing or not an object")

    for field in REQUIRED_TRACE_FIELDS:
        value = meta.get(field)
        if not isinstance(value, str) or not value:
            raise MissingTraceContext(f"trace_meta.{field} is missing or empty")

    return TraceMeta(
        trace_id=meta["trace_id"],
        parent_span_id=meta["parent_span_id"],
        session_id=meta.get("session_id", ""),
        run_id=meta.get("run_id", ""),
    )


def assert_trace_meta_present(event: dict[str, Any]) -> TraceMeta:
    """Thin wrapper for handlers that prefer an explicit assertion call."""
    return extract_trace_meta(event)
