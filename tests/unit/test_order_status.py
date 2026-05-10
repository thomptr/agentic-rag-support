"""Unit tests for order_status_lookup tool (T025 — must FAIL before implementation)."""

import pytest

from src.tools.definitions.order_status import (
    OrderStatusInput,
    OrderStatusOutput,
    order_status_lookup,
)


class TestOrderStatusLookup:
    def test_valid_order_returns_output(self):
        params = OrderStatusInput(order_id="ORD-12345")
        result = order_status_lookup(params)
        assert isinstance(result, OrderStatusOutput)
        assert result.order_id == "ORD-12345"
        assert result.status == "shipped"

    def test_all_required_fields_present(self):
        params = OrderStatusInput(order_id="ORD-12345")
        result = order_status_lookup(params)
        assert result.created_at
        assert result.updated_at
        assert isinstance(result.items, list)
        assert isinstance(result.total, float)

    def test_delivered_order(self):
        result = order_status_lookup(OrderStatusInput(order_id="ORD-12346"))
        assert result.status == "delivered"

    def test_unknown_order_raises_value_error(self):
        with pytest.raises(ValueError):
            order_status_lookup(OrderStatusInput(order_id="ORD-99999"))
