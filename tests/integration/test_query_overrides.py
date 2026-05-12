"""Integration tests for guardrails_enabled and model_override request fields."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    from src.api.main import app

    return TestClient(app)


def _mock_graph_result(guardrails_enabled=None, model_override=None):
    return {
        "response_text": "Test response.",
        "classified_domain": "billing",
        "classified_domains": ["billing"],
        "confidence_rationale": "test rationale",
        "current_node": "response_generator",
        "citations": [],
        "raw_retrieval_results": [],
        "merged_results": [],
        "retrieved_documents": [],
        "retrieval_confidence": {
            "score": 0.85,
            "result_count": 3,
            "avg_similarity": 0.85,
            "should_retry": False,
            "reason": "sufficient",
        },
        "retrieval_attempt": 1,
        "max_retrieval_attempts": 3,
        "log_events": [{"event_type": "llm_call"}],
        "tool_results": [],
        "pending_approvals": [],
        "action_taken": False,
        "guardrails_enabled": guardrails_enabled,
        "model_override": model_override,
    }


class TestQueryOverrides:
    @patch("src.graph.workflow.graph")
    def test_query_without_overrides_returns_200(self, mock_graph, client):
        mock_graph.invoke.return_value = _mock_graph_result()
        response = client.post("/query", json={"query_text": "Help with billing"})
        assert response.status_code == 200

    @patch("src.graph.workflow.graph")
    def test_guardrails_enabled_true_accepted(self, mock_graph, client):
        mock_graph.invoke.return_value = _mock_graph_result(guardrails_enabled=True)
        response = client.post(
            "/query",
            json={"query_text": "Help with billing", "guardrails_enabled": True},
        )
        assert response.status_code == 200
        _, kwargs = mock_graph.invoke.call_args
        state = mock_graph.invoke.call_args[0][0]
        assert state["guardrails_enabled"] is True

    @patch("src.graph.workflow.graph")
    def test_guardrails_enabled_false_accepted(self, mock_graph, client):
        mock_graph.invoke.return_value = _mock_graph_result(guardrails_enabled=False)
        response = client.post(
            "/query",
            json={"query_text": "Help with billing", "guardrails_enabled": False},
        )
        assert response.status_code == 200
        state = mock_graph.invoke.call_args[0][0]
        assert state["guardrails_enabled"] is False

    @patch("src.graph.workflow.graph")
    def test_guardrails_none_passes_none_to_graph(self, mock_graph, client):
        mock_graph.invoke.return_value = _mock_graph_result()
        response = client.post("/query", json={"query_text": "Help"})
        assert response.status_code == 200
        state = mock_graph.invoke.call_args[0][0]
        assert state["guardrails_enabled"] is None

    @patch("src.graph.workflow.graph")
    def test_model_override_gpt4o_mini_accepted(self, mock_graph, client):
        mock_graph.invoke.return_value = _mock_graph_result(model_override="gpt-4o-mini")
        response = client.post(
            "/query",
            json={"query_text": "Help", "model_override": "gpt-4o-mini"},
        )
        assert response.status_code == 200
        state = mock_graph.invoke.call_args[0][0]
        assert state["model_override"] == "gpt-4o-mini"

    @patch("src.graph.workflow.graph")
    def test_model_override_gpt4o_accepted(self, mock_graph, client):
        mock_graph.invoke.return_value = _mock_graph_result(model_override="gpt-4o")
        response = client.post(
            "/query",
            json={"query_text": "Help", "model_override": "gpt-4o"},
        )
        assert response.status_code == 200
        state = mock_graph.invoke.call_args[0][0]
        assert state["model_override"] == "gpt-4o"

    @patch("src.graph.workflow.graph")
    def test_model_override_claude_accepted(self, mock_graph, client):
        mock_graph.invoke.return_value = _mock_graph_result(model_override="claude-sonnet-4-6")
        response = client.post(
            "/query",
            json={"query_text": "Help", "model_override": "claude-sonnet-4-6"},
        )
        assert response.status_code == 200
        state = mock_graph.invoke.call_args[0][0]
        assert state["model_override"] == "claude-sonnet-4-6"

    def test_model_override_unknown_rejected(self, client):
        response = client.post(
            "/query",
            json={"query_text": "Help", "model_override": "gpt-5-turbo-illegal"},
        )
        assert response.status_code == 422

    @patch("src.graph.workflow.graph")
    def test_model_override_none_passes_none_to_graph(self, mock_graph, client):
        mock_graph.invoke.return_value = _mock_graph_result()
        response = client.post("/query", json={"query_text": "Help"})
        assert response.status_code == 200
        state = mock_graph.invoke.call_args[0][0]
        assert state["model_override"] is None

    @patch("src.graph.workflow.graph")
    def test_both_overrides_together(self, mock_graph, client):
        mock_graph.invoke.return_value = _mock_graph_result(
            guardrails_enabled=True, model_override="gpt-4o"
        )
        response = client.post(
            "/query",
            json={"query_text": "Help", "guardrails_enabled": True, "model_override": "gpt-4o"},
        )
        assert response.status_code == 200
        state = mock_graph.invoke.call_args[0][0]
        assert state["guardrails_enabled"] is True
        assert state["model_override"] == "gpt-4o"
