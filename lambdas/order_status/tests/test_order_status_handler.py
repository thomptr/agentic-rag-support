"""Contract + unit tests for the order_status Lambda handler.

TDD red — references `lambdas.order_status.handler` and `lambdas.order_status.schema`
(do not exist until T054, T055). Read-only tool; no idempotency test.
"""

from __future__ import annotations

import uuid

import pytest

try:
    from lambdas.order_status import schema as order_status_schema
    from lambdas.order_status.handler import lambda_handler
except ImportError as exc:
    pytest.skip(f"red — implementation missing: {exc}", allow_module_level=True)


def _trace_meta() -> dict:
    return {
        "trace_id": str(uuid.uuid4()),
        "parent_span_id": str(uuid.uuid4()),
        "session_id": "test-session",
        "run_id": "test-run",
    }


def _valid_event(**overrides) -> dict:
    event = {
        "tool_name": "order_status",
        "parameters": {"order_id": "ORD-12345"},
        "trace_meta": _trace_meta(),
    }
    event.update(overrides)
    return event


class TestOrderStatusHandler:
    def test_input_schema_matches_target_definition(self):
        params = order_status_schema.OrderStatusInput(order_id="ORD-1")
        assert params.order_id == "ORD-1"

    def test_missing_trace_context_returns_400(self):
        event = _valid_event()
        event.pop("trace_meta")
        result = lambda_handler(event, None)
        assert result["status"] == "error"
        assert result["error_code"] == "missing_trace_context"

    def test_wrong_tool_target_returns_400(self):
        event = _valid_event(tool_name="something_else")
        result = lambda_handler(event, None)
        assert result["status"] == "error"
        assert result["error_code"] == "wrong_tool_target"

    def test_happy_path_returns_success_envelope(self):
        event = _valid_event()
        result = lambda_handler(event, None)
        assert result["status"] == "success"
        assert result["trace_id"] == event["trace_meta"]["trace_id"]
        assert "status" in result["result"]  # the tool's payload status, not the envelope status
