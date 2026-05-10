"""create_support_ticket tool definition."""

from __future__ import annotations

from pydantic import BaseModel

from src.tools.backends.mock_tickets import create_ticket


class CreateTicketInput(BaseModel):
    subject: str
    description: str
    priority: str = "medium"
    category: str = "general"


class CreateTicketOutput(BaseModel):
    ticket_id: str
    status: str
    created_at: str


def create_support_ticket(params: CreateTicketInput) -> CreateTicketOutput:
    result = create_ticket(
        subject=params.subject,
        description=params.description,
        priority=params.priority,
        category=params.category,
    )
    return CreateTicketOutput(
        ticket_id=result["ticket_id"],
        status=result["status"],
        created_at=result["created_at"],
    )
