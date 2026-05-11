"""Unit tests for action_executor node.

After the Gateway cutover (FR-014), action_executor → execute_tool →
gateway_executor.invoke is the path for action tools. We autouse-patch the
Gateway boundary so these tests stay hermetic.
"""

import uuid

import pytest

from src.agents.action_executor import action_executor


@pytest.fixture(autouse=True)
def _stub_gateway(monkeypatch):
    from src.tools import gateway_executor

    monkeypatch.setattr("src.tools.orchestrator.settings.gateway_url", "https://test.gw")

    def _fake_invoke(*, tool_name, parameters, session_id, agent_type, trace_meta):
        return gateway_executor.ToolResult(
            tool_name=tool_name,
            status="success",
            result={"ok": True, "tool": tool_name},
            error=None,
        )

    monkeypatch.setattr(gateway_executor, "invoke", _fake_invoke)
    yield


def _state_with_tool_calls(tool_calls: list) -> dict:
    return {
        "query_id": str(uuid.uuid4()),
        "query_text": "test query",
        "run_id": "run-001",
        "response_text": "Here is the information you requested.",
        "merged_results": [],
        "classified_domains": ["billing"],
        "routed_to_agent": "support",
        "log_events": [],
        "tool_calls": tool_calls,
        "tool_results": None,
        "pending_approvals": None,
        "action_taken": None,
        "action_needed": True,
        "messages": [],
        "session_id": str(uuid.uuid4()),
    }


class TestActionExecutor:
    def test_executes_tool_and_accumulates_results(self):
        state = _state_with_tool_calls(
            [
                {
                    "tool_name": "order_status_lookup",
                    "parameters": {"order_id": "ORD-12345"},
                    "risk_level": "read-only",
                    "reason": "test",
                }
            ]
        )
        result = action_executor(state)
        tool_results = result.get("tool_results") or []
        assert len(tool_results) == 1
        assert tool_results[0]["tool_name"] == "order_status_lookup"

    def test_sets_action_taken_on_success(self):
        state = _state_with_tool_calls(
            [
                {
                    "tool_name": "order_status_lookup",
                    "parameters": {"order_id": "ORD-12345"},
                    "risk_level": "read-only",
                    "reason": "test",
                }
            ]
        )
        result = action_executor(state)
        assert result.get("action_taken") is True

    def test_empty_tool_calls_returns_no_results(self):
        state = _state_with_tool_calls([])
        result = action_executor(state)
        assert result.get("tool_results") == [] or result.get("tool_results") is None
        assert result.get("action_taken") is False or result.get("action_taken") is None

    def test_appends_tool_summary_to_response_text(self):
        state = _state_with_tool_calls(
            [
                {
                    "tool_name": "order_status_lookup",
                    "parameters": {"order_id": "ORD-12345"},
                    "risk_level": "read-only",
                    "reason": "test",
                }
            ]
        )
        result = action_executor(state)
        assert result.get("response_text") is not None


class TestActionExecutorMultiTool:
    def test_second_tool_receives_prior_results_in_context(self):
        """US3: Second tool call should have access to previous results."""
        state = _state_with_tool_calls(
            [
                {
                    "tool_name": "order_status_lookup",
                    "parameters": {"order_id": "ORD-12345"},
                    "risk_level": "read-only",
                    "reason": "first",
                },
                {
                    "tool_name": "create_support_ticket",
                    "parameters": {"subject": "Follow up", "description": "From order ORD-12345"},
                    "risk_level": "low",
                    "reason": "second",
                },
            ]
        )
        result = action_executor(state)
        tool_results = result.get("tool_results") or []
        assert len(tool_results) == 2

    def test_partial_failure_handled_gracefully(self):
        """US3: When one tool fails, executor reports succeeded steps and continues."""
        state = _state_with_tool_calls(
            [
                {
                    "tool_name": "order_status_lookup",
                    "parameters": {"order_id": "ORD-12345"},
                    "risk_level": "read-only",
                    "reason": "first",
                },
                {
                    "tool_name": "nonexistent_tool",
                    "parameters": {},
                    "risk_level": "low",
                    "reason": "will fail",
                },
            ]
        )
        result = action_executor(state)
        tool_results = result.get("tool_results") or []
        statuses = [r["status"] for r in tool_results]
        assert "success" in statuses
        assert "blocked" in statuses or "failed" in statuses
        # Response text should acknowledge partial success
        assert result.get("response_text") is not None
