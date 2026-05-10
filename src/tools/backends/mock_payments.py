"""Mock payment processor with 3 payment records and refund creation."""

from __future__ import annotations

from datetime import datetime, timezone

_PAYMENTS: dict[str, dict] = {
    "PAY-001": {
        "payment_id": "PAY-001",
        "order_id": "ORD-12345",
        "amount": 79.99,
        "status": "completed",
    },
    "PAY-002": {
        "payment_id": "PAY-002",
        "order_id": "ORD-12346",
        "amount": 149.50,
        "status": "completed",
    },
    "PAY-003": {
        "payment_id": "PAY-003",
        "order_id": "ORD-12347",
        "amount": 29.99,
        "status": "completed",
    },
}

_order_to_payment: dict[str, str] = {
    "ORD-12345": "PAY-001",
    "ORD-12346": "PAY-002",
    "ORD-12347": "PAY-003",
}

_refund_counter: int = 0
_refunds: dict[str, dict] = {}


def get_payment_for_order(order_id: str) -> dict | None:
    payment_id = _order_to_payment.get(order_id)
    if payment_id is None:
        return None
    return _PAYMENTS.get(payment_id)


def create_refund(
    order_id: str,
    amount: float,
    reason: str,
    fail_mode: str | None = None,
) -> dict:
    global _refund_counter
    if fail_mode == "service_unavailable":
        raise RuntimeError("Payment service unavailable (simulated)")
    _refund_counter += 1
    refund_id = f"REF-{_refund_counter:03d}"
    now = datetime.now(tz=timezone.utc).isoformat()
    refund = {
        "refund_id": refund_id,
        "order_id": order_id,
        "amount": amount,
        "reason": reason,
        "status": "processed",
        "processed_at": now,
    }
    _refunds[refund_id] = refund
    return refund


def get_refund(refund_id: str) -> dict | None:
    return _refunds.get(refund_id)
