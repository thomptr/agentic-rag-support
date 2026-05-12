"""create_ticket Lambda handler.

Contract: specs/005-aws-agentcore-deployment/contracts/tool-lambda.md
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import ValidationError

from lambdas.create_ticket.schema import CreateTicketInput, CreateTicketOutput
from lambdas.shared import audit_emitter, langfuse_client, responses, tracing

TOOL_NAME = "create_ticket"

# In-memory idempotency cache. The Lambda runtime keeps the interpreter warm
# between invocations on the same container, so duplicate calls within seconds
# usually hit the same cache. Containers are recycled (~15 min idle), so this
# is best-effort across cold starts — adequate for the POC. Upgrade to
# DynamoDB if true cross-container dedup matters.
_IDEMPOTENCY_TTL_S = 5 * 60
_idempotency_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _cached_result(key: str) -> dict | None:
    entry = _idempotency_cache.get(key)
    if entry is None:
        return None
    inserted_at, payload = entry
    if time.time() - inserted_at > _IDEMPOTENCY_TTL_S:
        _idempotency_cache.pop(key, None)
        return None
    return payload


def lambda_handler(event: dict, _context) -> dict:
    # --- Trace context validation ---
    try:
        trace_meta = tracing.extract_trace_meta(event)
    except tracing.MissingTraceContext as exc:
        return responses.error(
            "missing_trace_context",
            str(exc),
            trace_id=event.get("trace_meta", {}).get("trace_id", ""),
        )

    # --- Tool-name guard ---
    if event.get("tool_name") != TOOL_NAME:
        return responses.error(
            "wrong_tool_target",
            f"expected tool_name={TOOL_NAME!r}, got {event.get('tool_name')!r}",
            trace_id=trace_meta.trace_id,
        )

    # --- Parameter validation ---
    try:
        params = CreateTicketInput(**event.get("parameters", {}))
    except ValidationError as exc:
        return responses.error(
            "invalid_parameters",
            "; ".join(e["msg"] for e in exc.errors()),
            trace_id=trace_meta.trace_id,
            details={"errors": exc.errors()},
        )

    audit_emitter.log_tool_attempt(
        tool_name=TOOL_NAME,
        parameters=params.model_dump(),
        session_id=trace_meta.session_id,
        trace_id=trace_meta.trace_id,
    )

    span = langfuse_client.create_child_span(
        name=f"tool.{TOOL_NAME}",
        trace_meta=trace_meta,
        input_payload=params.model_dump(),
        metadata={"session_id": trace_meta.session_id, "run_id": trace_meta.run_id},
    )

    # --- Idempotency short-circuit ---
    if params.idempotency_key:
        cached = _cached_result(params.idempotency_key)
        if cached is not None:
            if span is not None:
                span.end(output={"cached": True, "result": cached["result"]})
            return cached

    # --- Mock business logic: generate a ticket ---
    start = time.perf_counter()
    output = CreateTicketOutput(
        ticket_id=f"TKT-{uuid.uuid4().hex[:8].upper()}",
        status="open",
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    duration_ms = (time.perf_counter() - start) * 1000

    envelope = responses.success(output.model_dump(), trace_id=trace_meta.trace_id)
    if params.idempotency_key:
        _idempotency_cache[params.idempotency_key] = (time.time(), envelope)

    audit_emitter.log_tool_success(
        tool_name=TOOL_NAME,
        result=output.model_dump(),
        session_id=trace_meta.session_id,
        trace_id=trace_meta.trace_id,
        duration_ms=duration_ms,
    )
    if span is not None:
        span.end(output=output.model_dump())
        langfuse_client.flush()
    return envelope
