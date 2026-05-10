"""order_status_lookup tool definition."""

from __future__ import annotations

from pydantic import BaseModel

from src.tools.backends.mock_orders import get_order


class OrderStatusInput(BaseModel):
    order_id: str


class OrderStatusOutput(BaseModel):
    order_id: str
    status: str
    created_at: str
    updated_at: str
    items: list[dict]
    total: float
    tracking_number: str | None


def order_status_lookup(params: OrderStatusInput) -> OrderStatusOutput:
    order = get_order(params.order_id)
    if order is None:
        raise ValueError(f"Order '{params.order_id}' not found")
    return OrderStatusOutput(
        order_id=order["order_id"],
        status=order["status"],
        created_at=order["created_at"],
        updated_at=order["updated_at"],
        items=order["items"],
        total=order["total"],
        tracking_number=order.get("tracking_number"),
    )
