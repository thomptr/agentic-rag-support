"""Pydantic models for the create_ticket Lambda.

Mirrors the in-process schema in `src/tools/definitions/create_ticket.py` and
adds `idempotency_key` per contracts/tool-lambda.md. The Lambda's input
validation matches the published MCP tool definition byte-for-byte; drift
between this file and the Gateway target schema is what
`test_input_schema_matches_target_definition` is locking.
"""

from __future__ import annotations

from pydantic import BaseModel


class CreateTicketInput(BaseModel):
    subject: str
    description: str
    priority: str = "medium"
    category: str = "general"
    idempotency_key: str | None = None


class CreateTicketOutput(BaseModel):
    ticket_id: str
    status: str
    created_at: str
