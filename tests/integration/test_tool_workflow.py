"""Integration tests for tool execution through the orchestrator.

These exercise guardrails + approval + dispatch end-to-end. After the Gateway
cutover (FR-014), the dispatch step routes through `gateway_executor.invoke`.
We autouse-patch that boundary so the tests stay hermetic (no live Gateway).
"""

import uuid

import pytest

from src.tools.guardrails import (
    _approval_store,
)
from src.tools.orchestrator import execute_tool


@pytest.fixture(autouse=True)
def _stub_gateway(monkeypatch):
    """Make all kind='gateway' dispatches succeed with a synthetic result.

    Returns shapes matching what the live Lambdas would emit so downstream
    assertions about `result` fields (ticket_id, order_id, refund_id) still
    have something realistic to read.
    """
    from src.tools import gateway_executor

    monkeypatch.setattr("src.tools.orchestrator.settings.gateway_url", "https://test.gw")

    _SYNTHETIC_RESULTS = {
        # status="shipped" matches the value the legacy in-process mock returned,
        # which several tests assert against.
        "order_status_lookup": {
            "order_id": "ORD-12346",
            "status": "shipped",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
            "items": [{"sku": "X", "qty": 1}],
            "total": 49.99,
            "tracking_number": "TRK-12346",
        },
        "create_support_ticket": {
            "ticket_id": "TKT-INTEG01",
            "status": "open",
            "created_at": "2026-01-01T00:00:00Z",
        },
        "issue_refund": {
            "refund_id": "REF-INTEG01",
            "order_id": "ORD-12346",
            "amount": 49.99,
            "status": "processed",
            "processed_at": "2026-01-01T00:00:00Z",
        },
    }

    def _fake_invoke(*, tool_name, parameters, session_id, agent_type, trace_meta):
        return gateway_executor.ToolResult(
            tool_name=tool_name,
            status="success",
            result=_SYNTHETIC_RESULTS.get(tool_name, {"ok": True}),
            error=None,
        )

    monkeypatch.setattr(gateway_executor, "invoke", _fake_invoke)
    yield


def _sid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# T039: US1 — Autonomous low-risk action execution
# ---------------------------------------------------------------------------


class TestUS1AutonomousExecution:
    def test_order_status_lookup_succeeds(self):
        result = execute_tool(
            tool_name="order_status_lookup",
            parameters={"order_id": "ORD-12345"},
            session_id=_sid(),
            agent_type="support",
        )
        assert result.status == "success"
        assert result.result["status"] == "shipped"
        assert result.block_reason is None

    def test_create_support_ticket_succeeds(self):
        result = execute_tool(
            tool_name="create_support_ticket",
            parameters={
                "subject": "Billing issue",
                "description": "Double charged on invoice",
                "priority": "high",
                "category": "billing",
            },
            session_id=_sid(),
            agent_type="support",
        )
        assert result.status == "success"
        assert result.result["ticket_id"].startswith("TKT-")
        assert result.result["status"] == "open"


# ---------------------------------------------------------------------------
# T055: US3 — Multi-tool sequencing
# ---------------------------------------------------------------------------


class TestUS3MultiToolSequencing:
    def test_order_lookup_then_ticket_creation(self):
        session_id = _sid()

        order_result = execute_tool(
            tool_name="order_status_lookup",
            parameters={"order_id": "ORD-12345"},
            session_id=session_id,
            agent_type="support",
        )
        assert order_result.status == "success"
        order_status = order_result.result["status"]

        ticket_result = execute_tool(
            tool_name="create_support_ticket",
            parameters={
                "subject": f"Issue with order ORD-12345 (status: {order_status})",
                "description": "Customer reported issue. Order status from lookup: " + order_status,
            },
            session_id=session_id,
            agent_type="support",
        )
        assert ticket_result.status == "success"
        assert ticket_result.result["ticket_id"].startswith("TKT-")

    def test_both_results_have_correct_structure(self):
        session_id = _sid()
        r1 = execute_tool("order_status_lookup", {"order_id": "ORD-12346"}, session_id, "support")
        r2 = execute_tool(
            "create_support_ticket",
            {
                "subject": "Delivered order follow-up",
                "description": f"Order delivered: {r1.result}",
            },
            session_id,
            "support",
        )
        assert r1.status == "success"
        assert r2.status == "success"


# ---------------------------------------------------------------------------
# T056: Rate limit blocks excess calls
# ---------------------------------------------------------------------------


class TestT056RateLimit:
    def test_excess_calls_blocked_after_rate_limit(self):
        session_id = _sid()
        # Use a very small limit by patching or calling many times with the default limit
        # Use a unique tool to not share rate limit state
        from src.tools.guardrails import RateLimitError, check_rate_limit

        limit = 3
        for _ in range(limit):
            check_rate_limit(session_id, "order_status_lookup_rl_test", limit=limit)

        with pytest.raises(RateLimitError):
            check_rate_limit(session_id, "order_status_lookup_rl_test", limit=limit)

    def test_blocked_result_has_correct_block_reason(self):
        session_id = _sid()

        # Override rate limit in registry temporarily
        from src.tools.registry import get_tool

        tool = get_tool("order_status_lookup")
        original_rate_limit = tool.rate_limit
        tool.rate_limit = 2

        try:
            execute_tool("order_status_lookup", {"order_id": "ORD-12345"}, session_id, "support")
            execute_tool("order_status_lookup", {"order_id": "ORD-12345"}, session_id, "support")
        except Exception:
            pass  # idempotency may block second call first

        # Third call should hit rate limit or idempotency
        result = execute_tool(
            "order_status_lookup", {"order_id": "ORD-12345"}, session_id, "support"
        )
        assert result.status == "blocked"
        assert result.block_reason in ("rate_limit", "duplicate_call")
        tool.rate_limit = original_rate_limit


# ---------------------------------------------------------------------------
# T057: Dollar cap blocks over-limit refunds
# ---------------------------------------------------------------------------


class TestT057DollarCap:
    def test_refund_exceeding_cap_is_blocked(self):
        from src.config import settings

        result = execute_tool(
            tool_name="issue_refund",
            parameters={
                "order_id": "ORD-12345",
                "amount": settings.tool_dollar_cap + 0.01,
                "reason": "testing cap",
            },
            session_id=_sid(),
            agent_type="support",
        )
        assert result.status == "blocked"
        assert result.block_reason == "dollar_cap"

    def test_refund_under_cap_routes_to_approval(self):
        result = execute_tool(
            tool_name="issue_refund",
            parameters={
                "order_id": "ORD-12345",
                "amount": 50.0,
                "reason": "defective",
            },
            session_id=_sid(),
            agent_type="support",
        )
        assert result.status == "pending_approval"
        assert result.approval_id is not None


# ---------------------------------------------------------------------------
# T058: Invalid params rejected before execution
# ---------------------------------------------------------------------------


class TestT058InvalidParams:
    def test_missing_required_param_blocked(self):
        result = execute_tool(
            tool_name="order_status_lookup",
            parameters={},
            session_id=_sid(),
            agent_type="support",
        )
        assert result.status == "blocked"
        assert result.block_reason == "invalid_params"

    def test_missing_refund_fields_blocked(self):
        result = execute_tool(
            tool_name="issue_refund",
            parameters={"order_id": "ORD-12345"},
            session_id=_sid(),
            agent_type="support",
        )
        assert result.status == "blocked"
        assert result.block_reason == "invalid_params"


# ---------------------------------------------------------------------------
# T059: check_refund_eligibility blocks cancelled/pending orders
# ---------------------------------------------------------------------------


class TestT059RefundEligibility:
    def test_cancelled_order_blocked_before_payment(self):
        result = execute_tool(
            tool_name="issue_refund",
            parameters={"order_id": "ORD-12348", "amount": 50.0, "reason": "cancelled"},
            session_id=_sid(),
            agent_type="support",
        )
        assert result.status == "blocked"
        assert result.block_reason == "refund_ineligible"

    def test_pending_order_blocked_before_payment(self):
        result = execute_tool(
            tool_name="issue_refund",
            parameters={"order_id": "ORD-12347", "amount": 20.0, "reason": "pending"},
            session_id=_sid(),
            agent_type="support",
        )
        assert result.status == "blocked"
        assert result.block_reason == "refund_ineligible"


# ---------------------------------------------------------------------------
# T060: High-risk tool routes to approval, not executed immediately
# ---------------------------------------------------------------------------


class TestT060HighRiskApprovalRouting:
    def test_refund_returns_pending_approval_not_executed(self):
        result = execute_tool(
            tool_name="issue_refund",
            parameters={"order_id": "ORD-12345", "amount": 50.0, "reason": "defective"},
            session_id=_sid(),
            agent_type="support",
        )
        assert result.status == "pending_approval"
        assert result.approval_id is not None
        assert result.result is None

    def test_pending_approval_stored_in_queue(self):
        result = execute_tool(
            tool_name="issue_refund",
            parameters={"order_id": "ORD-12345", "amount": 40.0, "reason": "wrong item"},
            session_id=_sid(),
            agent_type="support",
        )
        assert result.approval_id in _approval_store
        approval = _approval_store[result.approval_id]
        assert approval.status == "pending"


# ---------------------------------------------------------------------------
# T061: Expired approval returns 409
# ---------------------------------------------------------------------------


class TestT061ApprovalExpiry:
    def test_expired_approval_raises_on_approve(self):
        from datetime import datetime, timedelta, timezone

        from src.tools.guardrails import ApprovalRequest

        aid = str(uuid.uuid4())
        past = datetime.now(tz=timezone.utc) - timedelta(seconds=600)
        approval = ApprovalRequest(
            id=aid,
            tool_name="issue_refund",
            parameters={"order_id": "ORD-12345", "amount": 50.0, "reason": "expired"},
            requester_session="sess-expired",
            status="pending",
            created_at=past - timedelta(seconds=300),
            expires_at=past,
        )
        _approval_store[aid] = approval

        from src.tools.approval import approve

        with pytest.raises(ValueError) as exc_info:
            approve(aid, reviewer="admin", reason="too late")
        assert "expired" in str(exc_info.value).lower()
        assert _approval_store[aid].status == "expired"


# ---------------------------------------------------------------------------
# T062: Unregistered tool name rejected
# ---------------------------------------------------------------------------


class TestT062UnregisteredTool:
    def test_unknown_tool_blocked_before_execution(self):
        result = execute_tool(
            tool_name="completely_fake_tool",
            parameters={"key": "value"},
            session_id=_sid(),
            agent_type="support",
        )
        assert result.status == "blocked"
        assert result.block_reason == "unknown_tool"
        assert result.result is None
