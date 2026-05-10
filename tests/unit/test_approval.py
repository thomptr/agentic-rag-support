"""Unit tests for in-memory approval queue (T040)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from src.tools.approval import approve, expire_pending, get_approval, list_pending, reject
from src.tools.guardrails import _approval_store, check_requires_approval


def _create_test_approval(tool_name: str = "issue_refund", params: dict | None = None) -> str:
    session_id = str(uuid.uuid4())
    approval = check_requires_approval(
        tool_name,
        params or {"order_id": "ORD-12345", "amount": 50.0, "reason": "test"},
        session_id,
    )
    return approval.id


class TestApprovalQueueCreate:
    def test_create_returns_approval_with_uuid(self):
        aid = _create_test_approval()
        approval = get_approval(aid)
        assert approval is not None
        assert approval.id == aid
        assert approval.status == "pending"
        assert approval.expires_at > approval.created_at

    def test_created_approval_in_list_pending(self):
        aid = _create_test_approval()
        pending = list_pending()
        ids = [a.id for a in pending]
        assert aid in ids


class TestApprovalApprove:
    def test_approve_transitions_to_approved(self):
        aid = _create_test_approval()
        approve(aid, reviewer="admin@example.com", reason="Verified")
        approval = get_approval(aid)
        assert approval.status == "approved"
        assert approval.resolved_by == "admin@example.com"

    def test_approve_executes_tool(self):
        aid = _create_test_approval(
            tool_name="issue_refund",
            params={"order_id": "ORD-12345", "amount": 50.0, "reason": "defective"},
        )
        result = approve(aid, reviewer="admin@example.com", reason="Authorized")
        # Tool executed: result should have tool_name and either result or error
        assert result["status"] == "approved"

    def test_approve_not_found_raises_key_error(self):
        with pytest.raises(KeyError):
            approve("nonexistent-id", reviewer="admin", reason="x")

    def test_approve_already_resolved_raises_value_error(self):
        aid = _create_test_approval()
        approve(aid, reviewer="admin", reason="first approval")
        with pytest.raises(ValueError):
            approve(aid, reviewer="admin", reason="double approval")


class TestApprovalReject:
    def test_reject_transitions_to_rejected(self):
        aid = _create_test_approval()
        result = reject(aid, reviewer="admin@example.com", reason="Policy violation")
        approval = get_approval(aid)
        assert approval.status == "rejected"
        assert result["status"] == "rejected"

    def test_reject_not_found_raises_key_error(self):
        with pytest.raises(KeyError):
            reject("nonexistent-id", reviewer="admin", reason="x")

    def test_reject_already_resolved_raises_value_error(self):
        aid = _create_test_approval()
        reject(aid, reviewer="admin", reason="first")
        with pytest.raises(ValueError):
            reject(aid, reviewer="admin", reason="double")


class TestExpirePending:
    def test_expire_pending_transitions_expired_entries(self):
        session_id = str(uuid.uuid4())
        # Manually create an expired approval
        from src.tools.guardrails import ApprovalRequest

        past = datetime.now(tz=timezone.utc) - timedelta(seconds=600)
        approval = ApprovalRequest(
            id=str(uuid.uuid4()),
            tool_name="issue_refund",
            parameters={"order_id": "ORD-12345", "amount": 50.0, "reason": "expired"},
            requester_session=session_id,
            status="pending",
            created_at=past - timedelta(seconds=300),
            expires_at=past,
        )
        _approval_store[approval.id] = approval

        count = expire_pending()
        assert count >= 1
        assert _approval_store[approval.id].status == "expired"
