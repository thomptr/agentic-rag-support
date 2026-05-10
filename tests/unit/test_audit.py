"""Unit tests for audit logging helpers (T007 — must FAIL before implementation)."""

from src.tools.audit import (
    log_approval_requested,
    log_approval_resolved,
    log_tool_attempt,
    log_tool_blocked,
    log_tool_failed,
    log_tool_success,
)


class TestLogToolAttempt:
    def test_returns_dict_with_required_fields(self):
        event = log_tool_attempt(
            tool_name="order_status_lookup",
            parameters={"order_id": "ORD-001"},
            risk_level="read-only",
            session_id="sess-001",
        )
        assert event["event_type"] == "tool_call_attempt"
        assert event["tool_name"] == "order_status_lookup"
        assert event["parameters"] == {"order_id": "ORD-001"}
        assert event["risk_level"] == "read-only"
        assert event["session_id"] == "sess-001"


class TestLogToolSuccess:
    def test_returns_dict_with_required_fields(self):
        event = log_tool_success(
            tool_name="order_status_lookup",
            parameters={"order_id": "ORD-001"},
            result={"status": "shipped"},
            duration_ms=42.0,
            session_id="sess-001",
        )
        assert event["event_type"] == "tool_call_success"
        assert event["tool_name"] == "order_status_lookup"
        assert event["result"] == {"status": "shipped"}
        assert event["duration_ms"] == 42.0
        assert event["session_id"] == "sess-001"


class TestLogToolBlocked:
    def test_returns_dict_with_required_fields(self):
        event = log_tool_blocked(
            tool_name="issue_refund",
            parameters={"amount": 200.0},
            block_reason="dollar_cap",
            session_id="sess-001",
        )
        assert event["event_type"] == "tool_call_blocked"
        assert event["tool_name"] == "issue_refund"
        assert event["block_reason"] == "dollar_cap"
        assert event["session_id"] == "sess-001"


class TestLogToolFailed:
    def test_returns_dict_with_required_fields(self):
        event = log_tool_failed(
            tool_name="order_status_lookup",
            parameters={"order_id": "ORD-001"},
            error="backend unavailable",
            session_id="sess-001",
        )
        assert event["event_type"] == "tool_call_failed"
        assert event["tool_name"] == "order_status_lookup"
        assert event["error"] == "backend unavailable"
        assert event["session_id"] == "sess-001"


class TestLogApprovalRequested:
    def test_returns_dict_with_required_fields(self):
        event = log_approval_requested(
            approval_id="uuid-001",
            tool_name="issue_refund",
            parameters={"order_id": "ORD-001", "amount": 50.0},
            expires_at="2026-05-09T10:35:00Z",
            session_id="sess-001",
        )
        assert event["event_type"] == "approval_requested"
        assert event["approval_id"] == "uuid-001"
        assert event["tool_name"] == "issue_refund"
        assert event["expires_at"] == "2026-05-09T10:35:00Z"
        assert event["session_id"] == "sess-001"


class TestLogApprovalResolved:
    def test_returns_dict_with_required_fields(self):
        event = log_approval_resolved(
            approval_id="uuid-001",
            status="approved",
            resolved_by="admin@example.com",
            resolution_reason="Verified defective product",
        )
        assert event["event_type"] == "approval_resolved"
        assert event["approval_id"] == "uuid-001"
        assert event["status"] == "approved"
        assert event["resolved_by"] == "admin@example.com"
        assert event["resolution_reason"] == "Verified defective product"
