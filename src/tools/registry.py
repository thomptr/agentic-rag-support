"""Tool registry — central catalog of all registered tool definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel


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


_REGISTRY: dict[str, ToolDefinition] = {}


def _register(tool: ToolDefinition) -> None:
    _REGISTRY[tool.name] = tool


def _init_registry() -> None:
    from src.config import settings
    from src.tools.definitions.create_ticket import (
        CreateTicketInput,
        CreateTicketOutput,
        create_support_ticket,
    )
    from src.tools.definitions.issue_refund import (
        IssueRefundInput,
        IssueRefundOutput,
        issue_refund,
    )
    from src.tools.definitions.order_status import (
        OrderStatusInput,
        OrderStatusOutput,
        order_status_lookup,
    )

    _register(
        ToolDefinition(
            name="order_status_lookup",
            description="Look up the current status of a customer order by order ID.",
            input_schema=OrderStatusInput,
            output_schema=OrderStatusOutput,
            risk_level="read-only",
            execute_fn=order_status_lookup,
            rate_limit=None,
            dollar_cap=None,
            allowed_agents=["support"],
        )
    )
    _register(
        ToolDefinition(
            name="create_support_ticket",
            description="Create a new customer support ticket with subject, description, priority, and category.",
            input_schema=CreateTicketInput,
            output_schema=CreateTicketOutput,
            risk_level="low",
            execute_fn=create_support_ticket,
            rate_limit=None,
            dollar_cap=None,
            allowed_agents=["support"],
        )
    )
    _register(
        ToolDefinition(
            name="issue_refund",
            description="Issue a refund for a customer order. Requires human approval before execution.",
            input_schema=IssueRefundInput,
            output_schema=IssueRefundOutput,
            risk_level="high",
            execute_fn=issue_refund,
            rate_limit=None,
            dollar_cap=settings.tool_dollar_cap,
            allowed_agents=["support"],
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
