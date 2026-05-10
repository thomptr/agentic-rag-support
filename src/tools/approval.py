"""In-memory approval queue — manages high-risk action approval lifecycle."""

from __future__ import annotations

from datetime import datetime, timezone

from src.tools.executor import execute_tool
from src.tools.guardrails import ApprovalRequest, _approval_store


def create_approval(
    tool_name: str,
    parameters: dict,
    requester_session: str,
) -> ApprovalRequest:
    """Create and store a new ApprovalRequest. Returns the request."""
    from src.tools.guardrails import check_requires_approval

    return check_requires_approval(tool_name, parameters, requester_session)


def get_approval(approval_id: str) -> ApprovalRequest | None:
    return _approval_store.get(approval_id)


def approve(
    approval_id: str,
    reviewer: str,
    reason: str,
) -> dict:
    """Approve a pending action and execute the tool. Returns tool execution result dict."""
    approval = _approval_store.get(approval_id)
    if approval is None:
        raise KeyError(f"Approval request '{approval_id}' not found")
    if approval.status != "pending":
        raise ValueError(f"Approval request '{approval_id}' is already '{approval.status}'")

    now = datetime.now(tz=timezone.utc)
    if now > approval.expires_at:
        approval.status = "expired"
        raise ValueError(f"Approval request '{approval_id}' has expired")

    approval.status = "approved"
    approval.resolved_by = reviewer
    approval.resolution_reason = reason

    # Execute the tool now that it's approved
    result = execute_tool(
        tool_name=approval.tool_name,
        parameters=approval.parameters,
        session_id=approval.requester_session,
        agent_type="support",
    )

    from src.tools.audit import log_approval_resolved

    log_approval_resolved(
        approval_id=approval_id,
        status="approved",
        resolved_by=reviewer,
        resolution_reason=reason,
    )

    return {
        "id": approval_id,
        "status": "approved",
        "tool_name": approval.tool_name,
        "result": result.result,
        "error": result.error,
    }


def reject(
    approval_id: str,
    reviewer: str,
    reason: str,
) -> dict:
    """Reject a pending action."""
    approval = _approval_store.get(approval_id)
    if approval is None:
        raise KeyError(f"Approval request '{approval_id}' not found")
    if approval.status != "pending":
        raise ValueError(f"Approval request '{approval_id}' is already '{approval.status}'")

    approval.status = "rejected"
    approval.resolved_by = reviewer
    approval.resolution_reason = reason

    from src.tools.audit import log_approval_resolved

    log_approval_resolved(
        approval_id=approval_id,
        status="rejected",
        resolved_by=reviewer,
        resolution_reason=reason,
    )

    return {
        "id": approval_id,
        "status": "rejected",
        "reason": reason,
    }


def expire_pending() -> int:
    """Expire all pending approvals that have passed their expiry time. Returns count expired."""
    now = datetime.now(tz=timezone.utc)
    count = 0
    for approval in _approval_store.values():
        if approval.status == "pending" and now > approval.expires_at:
            approval.status = "expired"
            count += 1
    return count


def list_pending() -> list[ApprovalRequest]:
    expire_pending()
    return [a for a in _approval_store.values() if a.status == "pending"]
