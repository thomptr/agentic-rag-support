"""Pydantic models for the issue_refund Lambda.

Adds `customer_id` (Lambda-side authorization handle) and `idempotency_key`
versus the in-process schema in `src/tools/definitions/issue_refund.py`.
"""

from __future__ import annotations

from pydantic import BaseModel


class IssueRefundInput(BaseModel):
    order_id: str
    amount: float
    reason: str
    customer_id: str
    idempotency_key: str | None = None


class IssueRefundOutput(BaseModel):
    refund_id: str
    order_id: str
    amount: float
    status: str
    processed_at: str
