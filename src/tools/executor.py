"""Guardrail-wrapped tool executor — the single entry point for all tool calls."""

from __future__ import annotations

import time
from dataclasses import dataclass

from src.config import settings
from src.tools.audit import (
    log_approval_requested,
    log_tool_attempt,
    log_tool_blocked,
    log_tool_failed,
    log_tool_success,
)
from src.tools.guardrails import (
    CustomerIdMismatchError,
    DollarCapError,
    DuplicateToolCallError,
    InvalidParamsError,
    RateLimitError,
    RefundIneligibleError,
    UnknownToolError,
    check_dollar_cap,
    check_idempotency,
    check_rate_limit,
    check_refund_eligibility,
    check_requires_approval,
    check_risk_level,
    validate_agent_allowlist,
    validate_customer_id,
    validate_params,
)
from src.tools.registry import get_tool


@dataclass
class ToolResult:
    tool_name: str
    status: str  # "success" | "blocked" | "failed" | "pending_approval"
    result: dict | None
    error: str | None
    block_reason: str | None
    approval_id: str | None


def execute_tool(
    tool_name: str,
    parameters: dict,
    session_id: str,
    agent_type: str,
    session_customer_id: str | None = None,
) -> ToolResult:
    """Execute a tool through the full guardrail pipeline."""

    # --- Step 0: look up tool ---
    tool = get_tool(tool_name)
    if tool is None:
        log_tool_blocked(tool_name, parameters, "unknown_tool", session_id)
        return ToolResult(
            tool_name=tool_name,
            status="blocked",
            result=None,
            error=f"Tool '{tool_name}' is not registered",
            block_reason="unknown_tool",
            approval_id=None,
        )

    log_tool_attempt(tool_name, parameters, tool.risk_level, session_id)

    start = time.perf_counter()

    # --- Guard 1: agent allowlist ---
    try:
        validate_agent_allowlist(agent_type, tool_name, tool.allowed_agents)
    except UnknownToolError as exc:
        log_tool_blocked(tool_name, parameters, "unknown_tool", session_id)
        return ToolResult(tool_name, "blocked", None, str(exc), "unknown_tool", None)

    # --- Guard 2: params validation ---
    try:
        validated = validate_params(parameters, tool.input_schema)
    except InvalidParamsError as exc:
        log_tool_blocked(tool_name, parameters, "invalid_params", session_id)
        return ToolResult(tool_name, "blocked", None, str(exc), "invalid_params", None)

    # --- Guard 3: customer_id match ---
    if session_customer_id is not None:
        try:
            validate_customer_id(parameters, session_customer_id)
        except CustomerIdMismatchError as exc:
            log_tool_blocked(tool_name, parameters, "customer_id_mismatch", session_id)
            return ToolResult(tool_name, "blocked", None, str(exc), "customer_id_mismatch", None)

    # --- Guard 4: rate limit ---
    limit = tool.rate_limit if tool.rate_limit is not None else settings.tool_rate_limit_per_minute
    try:
        check_rate_limit(session_id, tool_name, limit)
    except RateLimitError as exc:
        log_tool_blocked(tool_name, parameters, "rate_limit", session_id)
        return ToolResult(tool_name, "blocked", None, str(exc), "rate_limit", None)

    # --- Guard 5: idempotency ---
    try:
        check_idempotency(session_id, tool_name, parameters)
    except DuplicateToolCallError as exc:
        log_tool_blocked(tool_name, parameters, "duplicate_call", session_id)
        return ToolResult(tool_name, "blocked", None, str(exc), "duplicate_call", None)

    # --- Guard 6: dollar cap (financial tools only) ---
    try:
        check_dollar_cap(parameters, tool.dollar_cap)
    except DollarCapError as exc:
        log_tool_blocked(tool_name, parameters, "dollar_cap", session_id)
        return ToolResult(tool_name, "blocked", None, str(exc), "dollar_cap", None)

    # --- Guard 7: refund eligibility (issue_refund only) ---
    if tool_name == "issue_refund":
        order_id = parameters.get("order_id")
        if order_id:
            try:
                check_refund_eligibility(order_id)
            except RefundIneligibleError as exc:
                log_tool_blocked(tool_name, parameters, "refund_ineligible", session_id)
                return ToolResult(tool_name, "blocked", None, str(exc), "refund_ineligible", None)

    # --- Guard 8: risk level routing ---
    routing = check_risk_level(tool.risk_level)

    # --- Guard 9: requires approval for high-risk ---
    if routing == "requires_approval":
        approval = check_requires_approval(tool_name, parameters, session_id)
        log_approval_requested(
            approval_id=approval.id,
            tool_name=tool_name,
            parameters=parameters,
            expires_at=approval.expires_at.isoformat(),
            session_id=session_id,
        )
        return ToolResult(
            tool_name=tool_name,
            status="pending_approval",
            result=None,
            error=None,
            block_reason=None,
            approval_id=approval.id,
        )

    # --- Execute tool ---
    try:
        raw_result = tool.execute_fn(validated)
        duration_ms = (time.perf_counter() - start) * 1000
        result_dict = (
            raw_result.model_dump() if hasattr(raw_result, "model_dump") else dict(raw_result)
        )
        log_tool_success(tool_name, parameters, result_dict, duration_ms, session_id)
        return ToolResult(
            tool_name=tool_name,
            status="success",
            result=result_dict,
            error=None,
            block_reason=None,
            approval_id=None,
        )
    except Exception as exc:
        duration_ms = (time.perf_counter() - start) * 1000
        log_tool_failed(tool_name, parameters, str(exc), session_id)
        return ToolResult(
            tool_name=tool_name,
            status="failed",
            result=None,
            error=str(exc),
            block_reason=None,
            approval_id=None,
        )
