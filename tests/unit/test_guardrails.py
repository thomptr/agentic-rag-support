"""Unit tests for all nine guardrail check functions (T005 — must FAIL before implementation)."""

import pytest
from pydantic import BaseModel

from src.tools.guardrails import (
    ApprovalRequest,
    CustomerIdMismatchError,
    DollarCapError,
    DuplicateToolCallError,
    InvalidParamsError,
    RateLimitError,
    RefundIneligibleError,
    UnknownToolError,
    check_dollar_cap,
    check_idempotency,
    check_rate_limit,
    check_refund_eligibility,
    check_requires_approval,
    check_risk_level,
    validate_agent_allowlist,
    validate_customer_id,
    validate_params,
)

# ---------------------------------------------------------------------------
# validate_agent_allowlist
# ---------------------------------------------------------------------------


class TestValidateAgentAllowlist:
    def test_known_agent_passes(self):
        validate_agent_allowlist("support", "order_status_lookup", ["support"])

    def test_unknown_agent_raises(self):
        with pytest.raises(UnknownToolError):
            validate_agent_allowlist("billing", "order_status_lookup", ["support"])

    def test_empty_allowlist_raises(self):
        with pytest.raises(UnknownToolError):
            validate_agent_allowlist("support", "order_status_lookup", [])


# ---------------------------------------------------------------------------
# validate_params
# ---------------------------------------------------------------------------


class _OrderInput(BaseModel):
    order_id: str


class TestValidateParams:
    def test_valid_params_returns_model(self):
        result = validate_params({"order_id": "ORD-001"}, _OrderInput)
        assert isinstance(result, _OrderInput)
        assert result.order_id == "ORD-001"

    def test_missing_required_field_raises(self):
        with pytest.raises(InvalidParamsError) as exc_info:
            validate_params({}, _OrderInput)
        assert "order_id" in str(exc_info.value).lower() or "field" in str(exc_info.value).lower()

    def test_wrong_type_raises(self):
        with pytest.raises(InvalidParamsError):
            validate_params({"order_id": 123}, _OrderInput)


# ---------------------------------------------------------------------------
# validate_customer_id
# ---------------------------------------------------------------------------


class TestValidateCustomerId:
    def test_matching_id_passes(self):
        validate_customer_id({"customer_id": "CUST-001"}, "CUST-001")

    def test_mismatched_id_raises(self):
        with pytest.raises(CustomerIdMismatchError):
            validate_customer_id({"customer_id": "CUST-999"}, "CUST-001")

    def test_missing_customer_id_passes(self):
        validate_customer_id({"order_id": "ORD-001"}, "CUST-001")


# ---------------------------------------------------------------------------
# check_risk_level
# ---------------------------------------------------------------------------


class TestCheckRiskLevel:
    def test_read_only_returns_proceed(self):
        assert check_risk_level("read-only") == "proceed"

    def test_low_returns_proceed(self):
        assert check_risk_level("low") == "proceed"

    def test_high_returns_requires_approval(self):
        assert check_risk_level("high") == "requires_approval"

    def test_unknown_tier_raises(self):
        with pytest.raises(ValueError):
            check_risk_level("critical")


# ---------------------------------------------------------------------------
# check_dollar_cap
# ---------------------------------------------------------------------------


class TestCheckDollarCap:
    def test_under_cap_passes(self):
        check_dollar_cap({"amount": 50.0}, 100.0)

    def test_at_cap_raises(self):
        with pytest.raises(DollarCapError):
            check_dollar_cap({"amount": 100.0}, 100.0)

    def test_over_cap_raises(self):
        with pytest.raises(DollarCapError):
            check_dollar_cap({"amount": 150.0}, 100.0)

    def test_no_cap_passes(self):
        check_dollar_cap({"amount": 999.0}, None)

    def test_no_amount_passes(self):
        check_dollar_cap({}, 100.0)


# ---------------------------------------------------------------------------
# check_refund_eligibility
# ---------------------------------------------------------------------------


class TestCheckRefundEligibility:
    def test_shipped_order_passes(self):
        check_refund_eligibility("ORD-12345")

    def test_delivered_order_passes(self):
        check_refund_eligibility("ORD-12346")

    def test_cancelled_order_raises(self):
        with pytest.raises(RefundIneligibleError) as exc_info:
            check_refund_eligibility("ORD-12348")
        assert "cancelled" in str(exc_info.value).lower()

    def test_pending_order_raises(self):
        with pytest.raises(RefundIneligibleError) as exc_info:
            check_refund_eligibility("ORD-12347")
        assert "pending" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# check_rate_limit
# ---------------------------------------------------------------------------


class TestCheckRateLimit:
    def test_first_call_passes(self):
        import uuid

        session_id = str(uuid.uuid4())
        check_rate_limit(session_id, "order_status_lookup", limit=5)

    def test_under_limit_passes(self):
        import uuid

        session_id = str(uuid.uuid4())
        for _ in range(4):
            check_rate_limit(session_id, "order_status_lookup", limit=5)

    def test_at_limit_raises(self):
        import uuid

        session_id = str(uuid.uuid4())
        for _ in range(5):
            check_rate_limit(session_id, "order_status_lookup", limit=5)
        with pytest.raises(RateLimitError):
            check_rate_limit(session_id, "order_status_lookup", limit=5)

    def test_different_sessions_are_independent(self):
        import uuid

        s1 = str(uuid.uuid4())
        s2 = str(uuid.uuid4())
        for _ in range(5):
            check_rate_limit(s1, "order_status_lookup", limit=5)
        # s2 should still pass
        check_rate_limit(s2, "order_status_lookup", limit=5)


# ---------------------------------------------------------------------------
# check_idempotency
# ---------------------------------------------------------------------------


class TestCheckIdempotency:
    def test_first_call_returns_key(self):
        import uuid

        session_id = str(uuid.uuid4())
        key = check_idempotency(session_id, "order_status_lookup", {"order_id": "ORD-001"})
        assert isinstance(key, str)
        assert len(key) > 0

    def test_duplicate_call_raises(self):
        import uuid

        session_id = str(uuid.uuid4())
        check_idempotency(session_id, "order_status_lookup", {"order_id": "ORD-001"})
        with pytest.raises(DuplicateToolCallError):
            check_idempotency(session_id, "order_status_lookup", {"order_id": "ORD-001"})

    def test_different_params_is_not_duplicate(self):
        import uuid

        session_id = str(uuid.uuid4())
        check_idempotency(session_id, "order_status_lookup", {"order_id": "ORD-001"})
        check_idempotency(session_id, "order_status_lookup", {"order_id": "ORD-002"})

    def test_same_params_different_session_passes(self):
        import uuid

        s1 = str(uuid.uuid4())
        s2 = str(uuid.uuid4())
        check_idempotency(s1, "order_status_lookup", {"order_id": "ORD-001"})
        check_idempotency(s2, "order_status_lookup", {"order_id": "ORD-001"})


# ---------------------------------------------------------------------------
# check_requires_approval
# ---------------------------------------------------------------------------


class TestCheckRequiresApproval:
    def test_returns_approval_request(self):
        import uuid

        session_id = str(uuid.uuid4())
        approval = check_requires_approval(
            "issue_refund",
            {"order_id": "ORD-12345", "amount": 79.99, "reason": "defective"},
            session_id,
        )
        assert isinstance(approval, ApprovalRequest)
        assert approval.id is not None
        assert approval.tool_name == "issue_refund"
        assert approval.status == "pending"
        assert approval.expires_at > approval.created_at
