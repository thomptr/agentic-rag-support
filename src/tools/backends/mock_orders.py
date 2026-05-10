"""Mock order database with 5 deterministic orders."""

from __future__ import annotations

_ORDERS: dict[str, dict] = {
    "ORD-12345": {
        "order_id": "ORD-12345",
        "status": "shipped",
        "created_at": "2026-04-01T10:00:00Z",
        "updated_at": "2026-04-03T08:00:00Z",
        "items": [
            {"name": "Widget A", "quantity": 2, "price": 29.99},
            {"name": "Widget B", "quantity": 1, "price": 20.01},
        ],
        "total": 79.99,
        "tracking_number": "TRK-ABC123",
    },
    "ORD-12346": {
        "order_id": "ORD-12346",
        "status": "delivered",
        "created_at": "2026-03-15T09:00:00Z",
        "updated_at": "2026-03-20T14:00:00Z",
        "items": [{"name": "Premium Kit", "quantity": 1, "price": 149.50}],
        "total": 149.50,
        "tracking_number": "TRK-DEF456",
    },
    "ORD-12347": {
        "order_id": "ORD-12347",
        "status": "pending",
        "created_at": "2026-05-08T16:00:00Z",
        "updated_at": "2026-05-08T16:00:00Z",
        "items": [{"name": "Basic Plan", "quantity": 1, "price": 29.99}],
        "total": 29.99,
        "tracking_number": None,
    },
    "ORD-12348": {
        "order_id": "ORD-12348",
        "status": "cancelled",
        "created_at": "2026-04-20T12:00:00Z",
        "updated_at": "2026-04-22T10:00:00Z",
        "items": [{"name": "Enterprise License", "quantity": 1, "price": 199.00}],
        "total": 199.00,
        "tracking_number": None,
    },
    "ORD-12349": {
        "order_id": "ORD-12349",
        "status": "shipped",
        "created_at": "2026-05-01T11:00:00Z",
        "updated_at": "2026-05-04T09:00:00Z",
        "items": [
            {"name": "Adapter", "quantity": 3, "price": 12.25},
            {"name": "Cable", "quantity": 1, "price": 18.00},
        ],
        "total": 54.75,
        "tracking_number": "TRK-GHI789",
    },
}


def get_order(order_id: str, fail_mode: str | None = None) -> dict | None:
    if fail_mode == "service_unavailable":
        raise RuntimeError("Order service unavailable (simulated)")
    return _ORDERS.get(order_id)


def list_orders() -> list[dict]:
    return list(_ORDERS.values())
