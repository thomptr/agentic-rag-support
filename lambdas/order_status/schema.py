"""Pydantic models for the order_status Lambda.

Read-only tool — no idempotency_key field.
"""

from __future__ import annotations

from pydantic import BaseModel


class OrderStatusInput(BaseModel):
    order_id: str


class OrderStatusOutput(BaseModel):
    order_id: str
    status: str
    created_at: str
    updated_at: str
    items: list[dict]
    total: float
    tracking_number: str | None = None
