"""Unit tests for action_planner node (T027 — must FAIL before implementation)."""

from unittest.mock import MagicMock, patch

from src.agents.action_planner import action_planner


def _make_state(query_text: str, response_text: str = "", merged_results: list | None = None):
    return {
        "query_id": "test-id",
        "query_text": query_text,
        "run_id": "run-001",
        "response_text": response_text,
        "merged_results": merged_results or [],
        "classified_domains": ["billing"],
        "current_node": "support",
        "log_events": [],
        "tool_calls": None,
        "tool_results": None,
        "pending_approvals": None,
        "action_taken": None,
        "action_needed": None,
    }


class TestActionPlanner:
    def test_returns_tool_calls_for_actionable_query(self):
        state = _make_state(
            query_text="What is the status of my order ORD-12345?",
            response_text="I can look up your order.",
        )
        with patch("src.agents.action_planner._get_llm") as mock_llm_fn:
            mock_llm = MagicMock()
            mock_llm_fn.return_value = mock_llm
            mock_structured = MagicMock()
            mock_llm.with_structured_output.return_value = mock_structured

            plan = MagicMock()
            plan.action_needed = True
            plan.tool_calls = [
                MagicMock(
                    tool_name="order_status_lookup",
                    parameters={"order_id": "ORD-12345"},
                    reason="Customer asked for order status",
                )
            ]
            mock_structured.invoke.return_value = plan

            result = action_planner(state)
            assert isinstance(result.get("tool_calls"), list)
            assert len(result["tool_calls"]) == 1
            assert result["tool_calls"][0]["tool_name"] == "order_status_lookup"

    def test_returns_empty_list_for_non_actionable_query(self):
        state = _make_state(
            query_text="How do I reset my password?",
            response_text="You can reset your password via settings.",
        )
        with patch("src.agents.action_planner._get_llm") as mock_llm_fn:
            mock_llm = MagicMock()
            mock_llm_fn.return_value = mock_llm
            mock_structured = MagicMock()
            mock_llm.with_structured_output.return_value = mock_structured

            plan = MagicMock()
            plan.action_needed = False
            plan.tool_calls = []
            mock_structured.invoke.return_value = plan

            result = action_planner(state)
            assert result.get("tool_calls") == []

    def test_passes_through_existing_tool_calls_without_calling_llm(self):
        """When the domain agent already emitted tool_calls via bind_tools,
        action_planner must NOT make a second LLM call — it should pass through."""
        state = _make_state(query_text="Refund please")
        state["tool_calls"] = [
            {
                "tool_name": "issue_refund",
                "parameters": {"order_id": "ORD-1", "amount": 10.0, "reason": "x"},
                "risk_level": "high",
                "reason": "llm-selected",
            }
        ]
        with patch("src.agents.action_planner._get_llm") as mock_llm_fn:
            result = action_planner(state)
            assert mock_llm_fn.call_count == 0
            assert result["tool_calls"] == state["tool_calls"]

    def test_uses_only_allowlisted_tools(self):
        """Tool calls from LLM should only contain tools that are in the registry."""
        state = _make_state(query_text="Order status for ORD-12345")
        with patch("src.agents.action_planner._get_llm") as mock_llm_fn:
            mock_llm = MagicMock()
            mock_llm_fn.return_value = mock_llm
            mock_structured = MagicMock()
            mock_llm.with_structured_output.return_value = mock_structured

            plan = MagicMock()
            plan.action_needed = True
            plan.tool_calls = [
                MagicMock(
                    tool_name="order_status_lookup",
                    parameters={"order_id": "ORD-12345"},
                    reason="Customer asked for order status",
                )
            ]
            mock_structured.invoke.return_value = plan

            result = action_planner(state)
            from src.tools.registry import get_registry

            registry = get_registry()
            for call in result.get("tool_calls", []):
                assert call["tool_name"] in registry
