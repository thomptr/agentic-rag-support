"""Unit tests for execute_tool() wrapper (T006 — must FAIL before implementation)."""

import uuid
from unittest.mock import MagicMock, patch

from src.tools.executor import ToolResult, execute_tool


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
        with patch("src.tools.executor.get_tool") as mock_get:
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
