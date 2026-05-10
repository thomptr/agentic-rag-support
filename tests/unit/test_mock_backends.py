"""Unit tests for mock backends (T023, T024, T041 — must FAIL before implementation)."""

import pytest

from src.tools.backends.mock_orders import get_order, list_orders
from src.tools.backends.mock_tickets import create_ticket, get_ticket


class TestMockOrders:
    def test_lookup_ord_12345_returns_shipped(self):
        order = get_order("ORD-12345")
        assert order is not None
        assert order["order_id"] == "ORD-12345"
        assert order["status"] == "shipped"

    def test_lookup_ord_12346_returns_delivered(self):
        order = get_order("ORD-12346")
        assert order["status"] == "delivered"

    def test_lookup_ord_12347_returns_pending(self):
        order = get_order("ORD-12347")
        assert order["status"] == "pending"

    def test_lookup_ord_12348_returns_cancelled(self):
        order = get_order("ORD-12348")
        assert order["status"] == "cancelled"

    def test_lookup_ord_12349_returns_shipped(self):
        order = get_order("ORD-12349")
        assert order["status"] == "shipped"

    def test_unknown_order_returns_none(self):
        assert get_order("ORD-99999") is None

    def test_fail_mode_raises(self):
        with pytest.raises(RuntimeError):
            get_order("ORD-12345", fail_mode="service_unavailable")

    def test_list_returns_five_orders(self):
        orders = list_orders()
        assert len(orders) == 5


class TestMockTickets:
    def test_create_ticket_returns_tkt_id(self):
        result = create_ticket("Test subject", "Test description")
        assert result["ticket_id"].startswith("TKT-")
        assert result["status"] == "open"

    def test_counter_increments(self):
        t1 = create_ticket("First", "First desc")
        t2 = create_ticket("Second", "Second desc")
        num1 = int(t1["ticket_id"].split("-")[1])
        num2 = int(t2["ticket_id"].split("-")[1])
        assert num2 == num1 + 1

    def test_ticket_stored_in_memory(self):
        result = create_ticket("Memory test", "desc")
        ticket_id = result["ticket_id"]
        stored = get_ticket(ticket_id)
        assert stored is not None
        assert stored["subject"] == "Memory test"

    def test_fail_mode_raises(self):
        with pytest.raises(RuntimeError):
            create_ticket("subject", "desc", fail_mode="service_unavailable")


class TestMockPayments:
    def test_lookup_payment_by_order_id(self):
        from src.tools.backends.mock_payments import get_payment_for_order

        payment = get_payment_for_order("ORD-12345")
        assert payment is not None
        assert payment["payment_id"] == "PAY-001"

    def test_create_refund_returns_ref_id(self):
        from src.tools.backends.mock_payments import create_refund

        result = create_refund("ORD-12345", 50.0, "defective product")
        assert result["refund_id"].startswith("REF-")
        assert result["amount"] == 50.0

    def test_refund_counter_increments(self):
        from src.tools.backends.mock_payments import create_refund

        r1 = create_refund("ORD-12345", 10.0, "reason1")
        r2 = create_refund("ORD-12346", 20.0, "reason2")
        num1 = int(r1["refund_id"].split("-")[1])
        num2 = int(r2["refund_id"].split("-")[1])
        assert num2 == num1 + 1

    def test_fail_mode_raises(self):
        from src.tools.backends.mock_payments import create_refund

        with pytest.raises(RuntimeError):
            create_refund("ORD-12345", 50.0, "reason", fail_mode="service_unavailable")
