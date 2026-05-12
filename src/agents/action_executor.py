"""action_executor node — guardrail-wrapped tool execution for each planned call."""

from __future__ import annotations

from src.graph.state import SupportGraphState
from src.tools.orchestrator import execute_tool


def action_executor(state: SupportGraphState) -> dict:
    """Execute each planned tool call through the guardrail pipeline."""
    tool_calls = state.get("tool_calls") or []
    agent_type = state.get("current_node") or "account_agent"
    session_id = state.get("session_id") or state.get("query_id") or "unknown"
    response_text = state.get("response_text") or ""

    # Per-request guardrails override (False = disable tool execution entirely)
    guardrails_enabled = state.get("guardrails_enabled")
    if guardrails_enabled is False:
        return {
            "tool_results": [],
            "pending_approvals": [],
            "action_taken": False,
            "log_events": [
                {
                    "event_type": "guardrails_disabled",
                    "message": "Tool execution disabled by request",
                }
            ],
        }

    if not tool_calls:
        return {
            "tool_results": [],
            "pending_approvals": [],
            "action_taken": False,
            "log_events": [],
        }

    tool_results: list[dict] = []
    pending_approvals: list[dict] = []
    prior_results: list[dict] = []
    any_success = False
    summaries: list[str] = []

    for call in tool_calls:
        tool_name = call.get("tool_name", "")
        parameters = call.get("parameters", {})

        result = execute_tool(
            tool_name=tool_name,
            parameters=parameters,
            session_id=session_id,
            agent_type=agent_type,
        )

        result_dict: dict = {
            "tool_name": result.tool_name,
            "parameters": parameters,
            "status": result.status,
            "result": result.result,
            "error": result.error,
            "block_reason": result.block_reason,
            "approval_id": result.approval_id,
        }
        tool_results.append(result_dict)
        prior_results.append(result_dict)

        if result.status == "success":
            any_success = True
            summaries.append(f"[{tool_name}] {_summarize_result(result.result)}")
        elif result.status == "pending_approval":
            from src.tools.guardrails import _approval_store

            approval = _approval_store.get(result.approval_id)
            if approval:
                pending_approvals.append(
                    {
                        "id": approval.id,
                        "tool_name": approval.tool_name,
                        "parameters": approval.parameters,
                        "status": approval.status,
                        "created_at": approval.created_at.isoformat(),
                        "expires_at": approval.expires_at.isoformat(),
                    }
                )
            summaries.append(
                f"[{tool_name}] Request submitted for human review (approval ID: {result.approval_id})"
            )
        elif result.status == "blocked":
            summaries.append(
                f"[{tool_name}] Action blocked: {result.block_reason} — {result.error}"
            )
        else:
            summaries.append(f"[{tool_name}] Failed: {result.error}")

    # Append tool result summaries to response text
    if summaries:
        tool_section = "\n\nAction Results:\n" + "\n".join(f"• {s}" for s in summaries)
        response_text = (response_text or "") + tool_section

    return {
        "tool_results": tool_results,
        "pending_approvals": pending_approvals if pending_approvals else [],
        "action_taken": any_success,
        "response_text": response_text,
        "log_events": [],
    }


def _summarize_result(result: dict | None) -> str:
    if not result:
        return "completed"
    if "status" in result and "order_id" in result:
        return f"Order {result['order_id']} is {result['status']}"
    if "ticket_id" in result:
        return f"Ticket {result['ticket_id']} created"
    if "refund_id" in result:
        return f"Refund {result['refund_id']} processed"
    return str(result)
