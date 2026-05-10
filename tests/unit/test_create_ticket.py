"""Unit tests for create_support_ticket tool (T026 — must FAIL before implementation)."""

from src.tools.definitions.create_ticket import (
    CreateTicketInput,
    CreateTicketOutput,
    create_support_ticket,
)


class TestCreateSupportTicket:
    def test_all_fields_set(self):
        params = CreateTicketInput(
            subject="Billing issue",
            description="Double charged",
            priority="high",
            category="billing",
        )
        result = create_support_ticket(params)
        assert isinstance(result, CreateTicketOutput)
        assert result.ticket_id.startswith("TKT-")
        assert result.status == "open"
        assert result.created_at

    def test_defaults_applied(self):
        params = CreateTicketInput(subject="Issue", description="desc")
        assert params.priority == "medium"
        assert params.category == "general"

    def test_returns_ticket_id(self):
        params = CreateTicketInput(subject="Test", description="test desc")
        result = create_support_ticket(params)
        assert result.ticket_id.startswith("TKT-")
