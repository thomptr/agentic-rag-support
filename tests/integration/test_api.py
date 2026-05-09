from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    from src.api.main import app

    return TestClient(app)


@patch("src.graph.workflow.graph")
def test_post_query_returns_200(mock_graph, client):
    mock_graph.invoke.return_value = {
        "query_id": "test-id",
        "response_text": "Your charge is explained by our pricing plan.",
        "classified_domain": "billing",
        "confidence_rationale": "billing charges",
        "routed_to_agent": "billing_agent",
        "citations": [
            {
                "doc_id": "d1",
                "chunk_text": "pricing plan text",
                "score": 0.9,
                "title": "Pricing Plans",
                "source_file": "docs/knowledge_base/billing/pricing-plans.md",
            }
        ],
        "retrieved_documents": [],
        "log_events": [
            {"event_type": "routing_decision"},
            {"event_type": "llm_call"},
            {"event_type": "retrieval"},
        ],
    }

    response = client.post("/query", json={"query_text": "Why was I charged twice?"})
    assert response.status_code == 200
    data = response.json()
    assert "query_id" in data
    assert "response_text" in data
    assert "citations" in data
    assert "metadata" in data


@patch("src.graph.workflow.graph")
def test_post_query_response_schema(mock_graph, client):
    mock_graph.invoke.return_value = {
        "response_text": "Technical answer",
        "classified_domain": "technical",
        "confidence_rationale": "API issue",
        "routed_to_agent": "technical_agent",
        "citations": [],
        "retrieved_documents": [],
        "log_events": [],
    }

    response = client.post("/query", json={"query_text": "How do I fix a 401 error?"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["query_id"], str)
    assert isinstance(data["response_text"], str)
    assert isinstance(data["citations"], list)
    assert isinstance(data["metadata"]["classified_domain"], (str, type(None)))
    assert isinstance(data["metadata"]["run_id"], str)
    assert isinstance(data["metadata"]["total_latency_ms"], float)


def test_post_query_returns_422_on_missing_query_text(client):
    response = client.post("/query", json={})
    assert response.status_code == 422


def test_post_query_returns_422_on_empty_string(client):
    response = client.post("/query", json={"query_text": "   "})
    assert response.status_code in (422, 400)


def test_get_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "vector_store" in data
    assert "llm" in data


def test_get_health_status_field(client):
    response = client.get("/health")
    assert response.json()["status"] == "healthy"
