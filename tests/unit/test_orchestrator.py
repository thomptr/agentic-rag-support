"""Unit tests for execute_tool() wrapper.

After the Gateway cutover (FR-014), kind="gateway" tools dispatch via
`src.tools.gateway_executor.invoke`. These tests autouse-patch that boundary
so they remain hermetic — they validate the executor's guardrails/approval
orchestration without standing up a real AgentCore Gateway.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from src.tools.orchestrator import ToolResult, execute_tool


@pytest.fixture(autouse=True)
def _stub_gateway(monkeypatch):
    """Make all kind='gateway' dispatches succeed with a synthetic result."""
    from src.tools import gateway_executor

    monkeypatch.setattr("src.tools.orchestrator.settings.gateway_url", "https://test.gw")

    def _fake_invoke(*, tool_name, parameters, session_id, agent_type, trace_meta):
        return gateway_executor.ToolResult(
            tool_name=tool_name,
            status="success",
            result={"order_id": parameters.get("order_id", "ORD-x"), "status": "delivered"},
            error=None,
        )

    monkeypatch.setattr(gateway_executor, "invoke", _fake_invoke)
    yield


class TestToolResult:
    def test_dataclass_fields(self):
        result = ToolResult(
            tool_name="order_status_lookup",
            status="success",
            result={"order_id": "ORD-001"},
            error=None,
            block_reason=None,
            approval_id=None,
        )
        assert result.tool_name == "order_status_lookup"
        assert result.status == "success"
        assert result.block_reason is None


class TestExecuteTool:
    def _session(self) -> str:
        return str(uuid.uuid4())

    def test_success_path_order_status(self):
        session_id = self._session()
        result = execute_tool(
            tool_name="order_status_lookup",
            parameters={"order_id": "ORD-12345"},
            session_id=session_id,
            agent_type="support",
        )
        assert result.status == "success"
        assert result.result is not None
        assert result.block_reason is None

    def test_unknown_tool_blocked(self):
        session_id = self._session()
        result = execute_tool(
            tool_name="nonexistent_tool",
            parameters={},
            session_id=session_id,
            agent_type="support",
        )
        assert result.status == "blocked"
        assert result.block_reason == "unknown_tool"

    def test_invalid_params_blocked(self):
        session_id = self._session()
        result = execute_tool(
            tool_name="order_status_lookup",
            parameters={},
            session_id=session_id,
            agent_type="support",
        )
        assert result.status == "blocked"
        assert result.block_reason == "invalid_params"

    def test_unauthorized_agent_blocked(self):
        session_id = self._session()
        result = execute_tool(
            tool_name="order_status_lookup",
            parameters={"order_id": "ORD-12345"},
            session_id=session_id,
            agent_type="billing",
        )
        assert result.status == "blocked"
        assert result.block_reason == "unknown_tool"

    def test_dollar_cap_blocked(self):
        session_id = self._session()
        result = execute_tool(
            tool_name="issue_refund",
            parameters={"order_id": "ORD-12345", "amount": 999.0, "reason": "test"},
            session_id=session_id,
            agent_type="support",
        )
        assert result.status == "blocked"
        assert result.block_reason == "dollar_cap"

    def test_high_risk_returns_pending_approval(self):
        session_id = self._session()
        result = execute_tool(
            tool_name="issue_refund",
            parameters={"order_id": "ORD-12345", "amount": 50.0, "reason": "defective"},
            session_id=session_id,
            agent_type="support",
        )
        assert result.status == "pending_approval"
        assert result.approval_id is not None

    def test_tool_execution_error_returns_failed(self):
        session_id = self._session()
        with patch("src.tools.orchestrator.get_tool") as mock_get:
            mock_tool = MagicMock()
            mock_tool.name = "order_status_lookup"
            mock_tool.risk_level = "read-only"
            mock_tool.rate_limit = 10
            mock_tool.dollar_cap = None
            mock_tool.allowed_agents = ["support"]
            mock_tool.input_schema = MagicMock()
            mock_tool.input_schema.model_validate = MagicMock(return_value=MagicMock())
            mock_tool.execute_fn = MagicMock(side_effect=RuntimeError("backend down"))
            mock_get.return_value = mock_tool

            result = execute_tool(
                tool_name="order_status_lookup",
                parameters={"order_id": "ORD-12345"},
                session_id=session_id,
                agent_type="support",
            )
        assert result.status == "failed"
        assert result.error is not None
