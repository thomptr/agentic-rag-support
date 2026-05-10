"""Unit tests for issue_refund tool (T042 — must FAIL before implementation)."""

from src.tools.definitions.issue_refund import (
    IssueRefundInput,
    IssueRefundOutput,
    issue_refund,
)


class TestIssueRefund:
    def test_valid_refund_returns_output(self):
        params = IssueRefundInput(
            order_id="ORD-12345",
            amount=50.0,
            reason="Defective product",
        )
        result = issue_refund(params)
        assert isinstance(result, IssueRefundOutput)
        assert result.refund_id.startswith("REF-")
        assert result.order_id == "ORD-12345"
        assert result.amount == 50.0
        assert result.status == "processed"
        assert result.processed_at


class TestIssueRefundGuardrailPath:
    """The tool itself doesn't enforce eligibility (that's done by the guardrail upstream).
    But the tool must correctly call the payment backend."""

    def test_unknown_order_still_processes_no_payment_found(self):
        params = IssueRefundInput(
            order_id="ORD-99999",
            amount=10.0,
            reason="test",
        )
        # The tool calls mock_payments.create_refund directly; no eligibility check here
        result = issue_refund(params)
        assert result.refund_id.startswith("REF-")
