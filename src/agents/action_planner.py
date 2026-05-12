"""action_planner node — LLM-based tool selection and parameter extraction."""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from src.config import settings
from src.graph.state import SupportGraphState
from src.tools.registry import get_tool_descriptions

_SYSTEM_PROMPT = """You are a customer support tool planner. Given the customer's query, the response already generated, and the available tools, decide if any tool actions should be taken.

Available tools are provided in the context. Only select tools that are directly relevant to the customer's request.

If no tool action is needed, set action_needed to false and return an empty tool_calls list.

Important rules:
- Only call tools when the customer explicitly requests an action (e.g., order lookup, ticket creation, refund)
- Do NOT call tools just to gather information that's already in the retrieved documents
- For order status queries, always extract the order ID from the query
- Return exact tool names as listed in the available tools"""


class PlannedToolCall(BaseModel):
    tool_name: str
    parameters: dict
    reason: str


class ToolCallPlan(BaseModel):
    action_needed: bool
    tool_calls: list[PlannedToolCall]


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(model=settings.llm_model, api_key=settings.openai_api_key)


def action_planner(state: SupportGraphState) -> dict:
    """Decide which tools (if any) to call based on the customer query and retrieved context."""
    # Domain agents now bind tools via OpenAI function-calling and may have
    # already produced structured tool_calls. If so, honor them and skip the
    # secondary planning LLM call — re-prompting would second-guess the model.
    existing = state.get("tool_calls")
    if existing:
        return {"tool_calls": existing, "log_events": []}

    query_text = state["query_text"]
    response_text = state.get("response_text") or ""
    agent_type = state.get("current_node") or "support"

    tool_descriptions = get_tool_descriptions(agent_type=agent_type)
    tools_json = json.dumps(tool_descriptions, indent=2)

    prompt = f"""Customer query: {query_text}

Response already generated:
{response_text}

Available tools:
{tools_json}

Based on the customer's query, determine if any tool actions should be taken. If the customer is asking for an order status, ticket creation, or refund, plan the appropriate tool call(s)."""

    llm = _get_llm()
    structured_llm = llm.with_structured_output(ToolCallPlan)

    try:
        plan: ToolCallPlan = structured_llm.invoke(
            [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        )
    except Exception:
        return {
            "tool_calls": [],
            "log_events": [],
        }

    if not plan.action_needed or not plan.tool_calls:
        return {
            "tool_calls": [],
            "log_events": [],
        }

    tool_calls = [
        {
            "tool_name": tc.tool_name,
            "parameters": tc.parameters,
            "risk_level": _get_risk_level(tc.tool_name),
            "reason": tc.reason,
        }
        for tc in plan.tool_calls
        if _is_registered(tc.tool_name)
    ]

    return {
        "tool_calls": tool_calls,
        "log_events": [],
    }


def _is_registered(tool_name: str) -> bool:
    from src.tools.registry import get_tool

    return get_tool(tool_name) is not None


def _get_risk_level(tool_name: str) -> str:
    from src.tools.registry import get_tool

    tool = get_tool(tool_name)
    return tool.risk_level if tool else "unknown"
