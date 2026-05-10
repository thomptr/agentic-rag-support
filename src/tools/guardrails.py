"""Guardrail pipeline — nine check functions executed before every tool call."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError

from src.config import settings

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Custom error types
# ---------------------------------------------------------------------------


class UnknownToolError(ValueError):
    pass


class InvalidParamsError(ValueError):
    pass


class CustomerIdMismatchError(PermissionError):
    pass


class RateLimitError(RuntimeError):
    pass


class DuplicateToolCallError(RuntimeError):
    pass


class DollarCapError(ValueError):
    pass


class RefundIneligibleError(ValueError):
    pass


# ---------------------------------------------------------------------------
# ApprovalRequest dataclass (used by check_requires_approval)
# ---------------------------------------------------------------------------


@dataclass
class ApprovalRequest:
    id: str
    tool_name: str
    parameters: dict
    requester_session: str
    status: str  # "pending" | "approved" | "rejected" | "expired"
    created_at: datetime
    expires_at: datetime
    resolved_by: str | None = None
    resolution_reason: str | None = None


# ---------------------------------------------------------------------------
# In-memory state for rate limiting and idempotency
# ---------------------------------------------------------------------------

# (session_id, tool_name) -> list of UTC timestamps
_rate_limit_store: dict[tuple[str, str], list[float]] = defaultdict(list)

# (session_id, tool_name, params_hash) -> idempotency key
_idempotency_store: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Guard 1: validate_agent_allowlist
# ---------------------------------------------------------------------------


def validate_agent_allowlist(agent_type: str, tool_name: str, allowed_agents: list[str]) -> None:
    """Raise UnknownToolError if agent_type is not in tool's allowed_agents."""
    if not allowed_agents or agent_type not in allowed_agents:
        raise UnknownToolError(
            f"Agent '{agent_type}' is not permitted to call tool '{tool_name}'. "
            f"Allowed agents: {allowed_agents}"
        )


# ---------------------------------------------------------------------------
# Guard 2: validate_params
# ---------------------------------------------------------------------------


def validate_params(parameters: dict, input_schema: type[BaseModel]) -> BaseModel:
    """Parse parameters with Pydantic; raise InvalidParamsError on failure."""
    try:
        return input_schema.model_validate(parameters)
    except (ValidationError, Exception) as exc:
        raise InvalidParamsError(f"Parameter validation failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Guard 3: validate_customer_id
# ---------------------------------------------------------------------------


def validate_customer_id(parameters: dict, session_customer_id: str) -> None:
    """Raise CustomerIdMismatchError if customer_id in params doesn't match the session."""
    param_customer_id = parameters.get("customer_id")
    if param_customer_id is None:
        return
    if param_customer_id != session_customer_id:
        raise CustomerIdMismatchError(
            f"customer_id in parameters ('{param_customer_id}') does not match "
            f"session customer_id ('{session_customer_id}')"
        )


# ---------------------------------------------------------------------------
# Guard 4: check_rate_limit
# ---------------------------------------------------------------------------


def check_rate_limit(session_id: str, tool_name: str, limit: int) -> None:
    """Sliding-window rate limiter — raises RateLimitError when limit reached."""
    import time

    key = (session_id, tool_name)
    now = time.time()
    window_start = now - 60.0

    timestamps = _rate_limit_store[key]
    # Prune old entries
    timestamps[:] = [t for t in timestamps if t >= window_start]

    if len(timestamps) >= limit:
        raise RateLimitError(
            f"Rate limit of {limit} calls/minute exceeded for tool '{tool_name}' "
            f"in session '{session_id}'"
        )
    timestamps.append(now)


# ---------------------------------------------------------------------------
# Guard 5: check_idempotency
# ---------------------------------------------------------------------------


def check_idempotency(session_id: str, tool_name: str, parameters: dict) -> str:
    """Return a new idempotency key on first call; raise DuplicateToolCallError on repeat."""
    params_hash = hashlib.sha256(
        json.dumps(
            {"session": session_id, "tool": tool_name, "params": parameters}, sort_keys=True
        ).encode()
    ).hexdigest()

    if params_hash in _idempotency_store:
        raise DuplicateToolCallError(
            f"Duplicate call detected: tool '{tool_name}' with same parameters "
            f"was already executed in session '{session_id}'"
        )
    _idempotency_store[params_hash] = session_id
    return params_hash


# ---------------------------------------------------------------------------
# Guard 6: check_dollar_cap
# ---------------------------------------------------------------------------


def check_dollar_cap(parameters: dict, dollar_cap: float | None) -> None:
    """Raise DollarCapError if parameters['amount'] exceeds dollar_cap."""
    if dollar_cap is None:
        return
    amount = parameters.get("amount")
    if amount is None:
        return
    if float(amount) >= dollar_cap:
        raise DollarCapError(f"Amount {amount} exceeds the configured dollar cap of {dollar_cap}")


# ---------------------------------------------------------------------------
# Guard 7: check_refund_eligibility
# ---------------------------------------------------------------------------


def check_refund_eligibility(order_id: str) -> None:
    """Raise RefundIneligibleError if the order is not in a refundable state."""
    from src.tools.backends.mock_orders import get_order

    order = get_order(order_id)
    if order is None:
        raise RefundIneligibleError(f"Order '{order_id}' not found")
    status = order["status"]
    if status == "cancelled":
        raise RefundIneligibleError(
            f"Order '{order_id}' cannot be refunded because it is cancelled"
        )
    if status == "pending":
        raise RefundIneligibleError(
            f"Order '{order_id}' cannot be refunded because it is still pending"
        )


# ---------------------------------------------------------------------------
# Guard 8: check_risk_level
# ---------------------------------------------------------------------------


def check_risk_level(risk_level: str) -> str:
    """Return 'proceed' for read-only/low, 'requires_approval' for high."""
    if risk_level in ("read-only", "low"):
        return "proceed"
    if risk_level == "high":
        return "requires_approval"
    raise ValueError(f"Unrecognized risk_level: '{risk_level}'")


# ---------------------------------------------------------------------------
# Guard 9: check_requires_approval
# ---------------------------------------------------------------------------

# In-memory store for approval requests (also used by approval.py)
_approval_store: dict[str, ApprovalRequest] = {}


def check_requires_approval(tool_name: str, parameters: dict, session_id: str) -> ApprovalRequest:
    """Create and store an ApprovalRequest; called when check_risk_level returns 'requires_approval'."""
    now = datetime.now(tz=timezone.utc)
    expires_at = now + timedelta(seconds=settings.approval_timeout_seconds)
    approval = ApprovalRequest(
        id=str(uuid.uuid4()),
        tool_name=tool_name,
        parameters=parameters,
        requester_session=session_id,
        status="pending",
        created_at=now,
        expires_at=expires_at,
    )
    _approval_store[approval.id] = approval
    return approval
