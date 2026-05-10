"""Mock ticketing system with counter-based ID generation."""

from __future__ import annotations

from datetime import datetime, timezone

_ticket_counter: int = 0
_tickets: dict[str, dict] = {}


def create_ticket(
    subject: str,
    description: str,
    priority: str = "medium",
    category: str = "general",
    fail_mode: str | None = None,
) -> dict:
    global _ticket_counter
    if fail_mode == "service_unavailable":
        raise RuntimeError("Ticket service unavailable (simulated)")
    _ticket_counter += 1
    ticket_id = f"TKT-{_ticket_counter:03d}"
    now = datetime.now(tz=timezone.utc).isoformat()
    ticket = {
        "ticket_id": ticket_id,
        "subject": subject,
        "description": description,
        "priority": priority,
        "category": category,
        "status": "open",
        "created_at": now,
    }
    _tickets[ticket_id] = ticket
    return ticket


def get_ticket(ticket_id: str) -> dict | None:
    return _tickets.get(ticket_id)


def list_tickets() -> list[dict]:
    return list(_tickets.values())
