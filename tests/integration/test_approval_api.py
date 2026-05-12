"""Integration test for the full approval workflow via FastAPI (T050)."""

import uuid

from fastapi.testclient import TestClient

from src.api.main import app
from src.tools.orchestrator import execute_tool

client = TestClient(app)


class TestApprovalWorkflowAPI:
    def test_list_approvals_returns_200(self):
        response = client.get("/approvals")
        assert response.status_code == 200
        data = response.json()
        assert "approvals" in data
        assert isinstance(data["approvals"], list)

    def test_approve_nonexistent_returns_404(self):
        response = client.post(
            "/approvals/nonexistent-id/approve",
            json={"reviewer": "admin@example.com", "reason": "test"},
        )
        assert response.status_code == 404

    def test_reject_nonexistent_returns_404(self):
        response = client.post(
            "/approvals/nonexistent-id/reject",
            json={"reviewer": "admin@example.com", "reason": "test"},
        )
        assert response.status_code == 404

    def test_full_approval_lifecycle(self):
        """Create approval → list → approve → verify result."""
        session_id = str(uuid.uuid4())
        tool_result = execute_tool(
            tool_name="issue_refund",
            parameters={"order_id": "ORD-12345", "amount": 60.0, "reason": "defective product"},
            session_id=session_id,
            agent_type="billing_agent",
        )
        assert tool_result.status == "pending_approval"
        approval_id = tool_result.approval_id

        # List approvals — should contain our new one
        list_resp = client.get("/approvals")
        assert list_resp.status_code == 200
        ids = [a["id"] for a in list_resp.json()["approvals"]]
        assert approval_id in ids

        # Approve it
        approve_resp = client.post(
            f"/approvals/{approval_id}/approve",
            json={"reviewer": "admin@example.com", "reason": "Verified defective product"},
        )
        assert approve_resp.status_code == 200
        data = approve_resp.json()
        assert data["status"] == "approved"
        assert data["id"] == approval_id

    def test_double_approve_returns_409(self):
        session_id = str(uuid.uuid4())
        tool_result = execute_tool(
            tool_name="issue_refund",
            parameters={"order_id": "ORD-12345", "amount": 30.0, "reason": "wrong item"},
            session_id=session_id,
            agent_type="billing_agent",
        )
        approval_id = tool_result.approval_id

        client.post(
            f"/approvals/{approval_id}/approve",
            json={"reviewer": "admin@example.com", "reason": "first"},
        )
        second = client.post(
            f"/approvals/{approval_id}/approve",
            json={"reviewer": "admin@example.com", "reason": "second"},
        )
        assert second.status_code == 409

    def test_reject_workflow(self):
        session_id = str(uuid.uuid4())
        tool_result = execute_tool(
            tool_name="issue_refund",
            parameters={"order_id": "ORD-12345", "amount": 25.0, "reason": "dissatisfied"},
            session_id=session_id,
            agent_type="billing_agent",
        )
        approval_id = tool_result.approval_id

        reject_resp = client.post(
            f"/approvals/{approval_id}/reject",
            json={"reviewer": "admin@example.com", "reason": "Amount exceeds policy"},
        )
        assert reject_resp.status_code == 200
        data = reject_resp.json()
        assert data["status"] == "rejected"
        assert data["id"] == approval_id
