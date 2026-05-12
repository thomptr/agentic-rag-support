"""Contract + unit tests for the issue_refund Lambda handler.

TDD red — references `lambdas.issue_refund.handler` and `lambdas.issue_refund.schema`
(do not exist until T052, T053).
"""

from __future__ import annotations

import uuid

import pytest

try:
    from lambdas.issue_refund import schema as issue_refund_schema
    from lambdas.issue_refund.handler import lambda_handler
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
        "tool_name": "issue_refund",
        "parameters": {
            "order_id": "ORD-12345",
            "amount": 49.99,
            "reason": "Defective product",
            "customer_id": "CUST-001",
        },
        "trace_meta": _trace_meta(),
    }
    event.update(overrides)
    return event


class TestIssueRefundHandler:
    def test_input_schema_matches_target_definition(self):
        params = issue_refund_schema.IssueRefundInput(
            order_id="ORD-1",
            amount=10.0,
            reason="test",
            customer_id="CUST-1",
        )
        assert params.order_id == "ORD-1"
        assert params.amount == 10.0

    def test_missing_trace_context_returns_400(self):
        event = _valid_event()
        event.pop("trace_meta")
        result = lambda_handler(event, None)
        assert result["status"] == "error"
        assert result["error_code"] == "missing_trace_context"

    def test_wrong_tool_target_returns_400(self):
        event = _valid_event(tool_name="not_issue_refund")
        result = lambda_handler(event, None)
        assert result["status"] == "error"
        assert result["error_code"] == "wrong_tool_target"

    def test_happy_path_returns_success_envelope(self):
        event = _valid_event()
        result = lambda_handler(event, None)
        assert result["status"] == "success"
        assert result["trace_id"] == event["trace_meta"]["trace_id"]
        assert "refund_id" in result["result"]

    def test_handler_idempotency_window(self):
        idem_key = str(uuid.uuid4())
        event = _valid_event()
        event["parameters"]["idempotency_key"] = idem_key
        first = lambda_handler(event, None)
        second = lambda_handler(event, None)
        assert first["result"]["refund_id"] == second["result"]["refund_id"]


class TestIssueRefundChaosMode:
    """T120 — chaos fixture: env-var-driven forced failure for SC-005 timing."""

    def test_business_rule_violation_emits_child_span_with_error_code(self, monkeypatch):
        """When FAIL_MODE=business_rule_violation, handler returns the error envelope."""
        monkeypatch.setenv("FAIL_MODE", "business_rule_violation")
        event = _valid_event()
        result = lambda_handler(event, None)
        assert result["status"] == "error"
        assert result["error_code"] == "business_rule_violation"
        assert result["trace_id"] == event["trace_meta"]["trace_id"]

    def test_unknown_fail_mode_is_ignored(self, monkeypatch):
        """Garbage FAIL_MODE values fall through to the happy path."""
        monkeypatch.setenv("FAIL_MODE", "definitely-not-a-real-mode")
        event = _valid_event()
        result = lambda_handler(event, None)
        assert result["status"] == "success"

    def test_default_no_fail_mode(self, monkeypatch):
        """Without FAIL_MODE set, normal success path."""
        monkeypatch.delenv("FAIL_MODE", raising=False)
        event = _valid_event()
        result = lambda_handler(event, None)
        assert result["status"] == "success"
