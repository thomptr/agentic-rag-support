"""order_status Lambda handler — read-only order lookup.

Contract: specs/005-aws-agentcore-deployment/contracts/tool-lambda.md
"""

from __future__ import annotations

import time

from pydantic import ValidationError

from lambdas.order_status.schema import OrderStatusInput, OrderStatusOutput
from lambdas.shared import audit_emitter, langfuse_client, responses, tracing

TOOL_NAME = "order_status"


def lambda_handler(event: dict, _context) -> dict:
    try:
        trace_meta = tracing.extract_trace_meta(event)
    except tracing.MissingTraceContext as exc:
        return responses.error(
            "missing_trace_context",
            str(exc),
            trace_id=event.get("trace_meta", {}).get("trace_id", ""),
        )

    if event.get("tool_name") != TOOL_NAME:
        return responses.error(
            "wrong_tool_target",
            f"expected tool_name={TOOL_NAME!r}, got {event.get('tool_name')!r}",
            trace_id=trace_meta.trace_id,
        )

    try:
        params = OrderStatusInput(**event.get("parameters", {}))
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

    start = time.perf_counter()
    # Mock order data — no external dependency.
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    output = OrderStatusOutput(
        order_id=params.order_id,
        status="shipped",
        created_at=now,
        updated_at=now,
        items=[{"sku": "ITEM-1", "qty": 1, "name": "Sample item"}],
        total=49.99,
        tracking_number=f"TRK-{params.order_id[-6:]}",
    )
    duration_ms = (time.perf_counter() - start) * 1000

    envelope = responses.success(output.model_dump(), trace_id=trace_meta.trace_id)

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
