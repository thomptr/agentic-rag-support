"""Audit logging helpers for tool execution events."""

import structlog

_log = structlog.get_logger()


def log_tool_attempt(
    tool_name: str,
    parameters: dict,
    risk_level: str,
    session_id: str,
) -> dict:
    event = {
        "event_type": "tool_call_attempt",
        "tool_name": tool_name,
        "parameters": parameters,
        "risk_level": risk_level,
        "session_id": session_id,
    }
    _log.info("tool_call_attempt", **event)
    return event


def log_tool_success(
    tool_name: str,
    parameters: dict,
    result: dict,
    duration_ms: float,
    session_id: str,
) -> dict:
    event = {
        "event_type": "tool_call_success",
        "tool_name": tool_name,
        "parameters": parameters,
        "result": result,
        "duration_ms": duration_ms,
        "session_id": session_id,
    }
    _log.info("tool_call_success", **event)
    return event


def log_tool_blocked(
    tool_name: str,
    parameters: dict,
    block_reason: str,
    session_id: str,
) -> dict:
    event = {
        "event_type": "tool_call_blocked",
        "tool_name": tool_name,
        "parameters": parameters,
        "block_reason": block_reason,
        "session_id": session_id,
    }
    _log.info("tool_call_blocked", **event)
    return event


def log_tool_failed(
    tool_name: str,
    parameters: dict,
    error: str,
    session_id: str,
) -> dict:
    event = {
        "event_type": "tool_call_failed",
        "tool_name": tool_name,
        "parameters": parameters,
        "error": error,
        "session_id": session_id,
    }
    _log.info("tool_call_failed", **event)
    return event


def log_approval_requested(
    approval_id: str,
    tool_name: str,
    parameters: dict,
    expires_at: str,
    session_id: str,
) -> dict:
    event = {
        "event_type": "approval_requested",
        "approval_id": approval_id,
        "tool_name": tool_name,
        "parameters": parameters,
        "expires_at": expires_at,
        "session_id": session_id,
    }
    _log.info("approval_requested", **event)
    return event


def log_approval_resolved(
    approval_id: str,
    status: str,
    resolved_by: str,
    resolution_reason: str,
) -> dict:
    event = {
        "event_type": "approval_resolved",
        "approval_id": approval_id,
        "status": status,
        "resolved_by": resolved_by,
        "resolution_reason": resolution_reason,
    }
    _log.info("approval_resolved", **event)
    return event
