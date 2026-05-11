"""Tool registry — central catalog of all registered tool definitions.

Schemas for the three action tools (create_support_ticket, issue_refund,
order_status_lookup) are inlined here. The in-process execute_fn callables
were removed when the executor was cut over to the Gateway (FR-014); the
agent still needs the schemas for in-process guardrails (validate_params,
schema-driven LLM tool discovery). Drift between these schemas and
`lambdas/<tool>/schema.py` is locked by the per-Lambda contract tests
(T030/T032/T033).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel


# ── Inline schemas (formerly in src/tools/definitions/) ───────────────────────
class CreateTicketInput(BaseModel):
    subject: str
    description: str
    priority: str = "medium"
    category: str = "general"


class CreateTicketOutput(BaseModel):
    ticket_id: str
    status: str
    created_at: str


class IssueRefundInput(BaseModel):
    order_id: str
    amount: float
    reason: str


class IssueRefundOutput(BaseModel):
    refund_id: str
    order_id: str
    amount: float
    status: str
    processed_at: str


class OrderStatusInput(BaseModel):
    order_id: str


class OrderStatusOutput(BaseModel):
    order_id: str
    status: str
    created_at: str
    updated_at: str
    items: list[dict]
    total: float
    tracking_number: str | None = None


def _gateway_only_stub(params: Any):
    """Placeholder execute_fn for Gateway-routed tools.

    The legacy executor.py orchestration looks up `tool.execute_fn` and calls
    it as a fallback. With the Gateway active, kind="gateway" tools never
    reach this code path — they're dispatched via gateway_executor.invoke().
    If this stub is ever called, something has bypassed the routing.
    """
    raise NotImplementedError(
        "Gateway-routed tool was dispatched to its execute_fn stub. "
        "Check that settings.gateway_url is set and the executor's "
        "kind=='gateway' branch is active."
    )


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    risk_level: str  # "read-only" | "low" | "high"
    execute_fn: Callable
    rate_limit: int | None
    dollar_cap: float | None
    allowed_agents: list[str]
    # "in_process" (run execute_fn locally) or "gateway" (dispatch via AgentCore
    # Tool Gateway). Defaults to in_process to preserve behavior for callers that
    # don't set it; the three action tools below are tagged "gateway" so the
    # executor knows to route their dispatch step through gateway_executor.
    kind: str = "in_process"


_REGISTRY: dict[str, ToolDefinition] = {}


def _register(tool: ToolDefinition) -> None:
    _REGISTRY[tool.name] = tool


def _init_registry() -> None:
    from src.config import settings

    _register(
        ToolDefinition(
            name="order_status_lookup",
            description="Look up the current status of a customer order by order ID.",
            input_schema=OrderStatusInput,
            output_schema=OrderStatusOutput,
            risk_level="read-only",
            execute_fn=_gateway_only_stub,
            rate_limit=None,
            dollar_cap=None,
            allowed_agents=["support"],
            kind="gateway",
        )
    )
    _register(
        ToolDefinition(
            name="create_support_ticket",
            description="Create a new customer support ticket with subject, description, priority, and category.",
            input_schema=CreateTicketInput,
            output_schema=CreateTicketOutput,
            risk_level="low",
            execute_fn=_gateway_only_stub,
            rate_limit=None,
            dollar_cap=None,
            allowed_agents=["support"],
            kind="gateway",
        )
    )
    _register(
        ToolDefinition(
            name="issue_refund",
            description="Issue a refund for a customer order. Requires human approval before execution.",
            input_schema=IssueRefundInput,
            output_schema=IssueRefundOutput,
            risk_level="high",
            execute_fn=_gateway_only_stub,
            rate_limit=None,
            dollar_cap=settings.tool_dollar_cap,
            allowed_agents=["support"],
            kind="gateway",
        )
    )


_init_registry()


def get_registry() -> dict[str, ToolDefinition]:
    return dict(_REGISTRY)


def get_tool(name: str) -> ToolDefinition | None:
    return _REGISTRY.get(name)


def get_tool_descriptions(agent_type: str | None = None) -> list[dict]:
    tools = list(_REGISTRY.values())
    if agent_type is not None:
        tools = [t for t in tools if agent_type in t.allowed_agents]
    result = []
    for tool in tools:
        schema = tool.input_schema.model_json_schema()
        result.append(
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": schema,
                "risk_level": tool.risk_level,
            }
        )
    return result
