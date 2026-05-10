"""issue_refund tool definition."""

from __future__ import annotations

from pydantic import BaseModel

from src.tools.backends.mock_payments import create_refund


class IssueRefundInput(BaseModel):
    order_id: str
    amount: float
    reason: str


class IssueRefundOutput(BaseModel):
    refund_id: str
    order_id: str
    amount: float
    status: str
    processed_at: str


def issue_refund(params: IssueRefundInput) -> IssueRefundOutput:
    result = create_refund(
        order_id=params.order_id,
        amount=params.amount,
        reason=params.reason,
    )
    return IssueRefundOutput(
        refund_id=result["refund_id"],
        order_id=result["order_id"],
        amount=result["amount"],
        status=result["status"],
        processed_at=result["processed_at"],
    )
