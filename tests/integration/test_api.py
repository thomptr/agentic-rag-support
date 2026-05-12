from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    from src.api.main import app

    return TestClient(app)


def _mock_graph_result(
    classified_domains=None,
    retrieval_attempt=1,
    response_text="Your answer.",
    citations=None,
    raw_retrieval_results=None,
    merged_results=None,
    retrieval_confidence_score=0.85,
):
    return {
        "response_text": response_text,
        "classified_domain": (classified_domains or ["billing"])[0],
        "classified_domains": classified_domains or ["billing"],
        "confidence_rationale": "test rationale",
        "current_node": "response_generator",
        "citations": citations
        or [
            {
                "content": "Pricing plan text",
                "domain": "billing",
                "source": "pricing-plans.md",
                "score": 0.9,
                "doc_id": "d1",
                "chunk_text": "pricing plan text",
                "title": "Pricing Plans",
                "source_file": "pricing-plans.md",
            }
        ],
        "raw_retrieval_results": raw_retrieval_results or [],
        "merged_results": merged_results or [],
        "retrieved_documents": merged_results or [],
        "retrieval_confidence": {
            "score": retrieval_confidence_score,
            "result_count": 5,
            "avg_similarity": retrieval_confidence_score,
            "should_retry": False,
            "reason": "sufficient confidence",
        },
        "retrieval_attempt": retrieval_attempt,
        "max_retrieval_attempts": 3,
        "log_events": [
            {"event_type": "routing_decision"},
            {"event_type": "llm_call"},
            {"event_type": "multi_retrieval"},
        ],
    }


# --- T042: Updated API response schema tests ---


@patch("src.graph.workflow.graph")
def test_post_query_returns_200(mock_graph, client):
    mock_graph.invoke.return_value = _mock_graph_result()

    response = client.post("/query", json={"query_text": "Why was I charged twice?"})
    assert response.status_code == 200
    data = response.json()
    assert "query_id" in data
    assert "response_text" in data
    assert "citations" in data
    assert "metadata" in data


@patch("src.graph.workflow.graph")
def test_post_query_returns_classified_domains(mock_graph, client):
    mock_graph.invoke.return_value = _mock_graph_result(classified_domains=["billing", "account"])

    response = client.post(
        "/query", json={"query_text": "I was charged twice and my account is locked"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "classified_domains" in data["metadata"]
    assert isinstance(data["metadata"]["classified_domains"], list)
    assert len(data["metadata"]["classified_domains"]) == 2


@patch("src.graph.workflow.graph")
def test_post_query_returns_retrieval_attempts(mock_graph, client):
    mock_graph.invoke.return_value = _mock_graph_result(retrieval_attempt=2)

    response = client.post("/query", json={"query_text": "difficult query"})
    assert response.status_code == 200
    data = response.json()
    assert "retrieval_attempts" in data["metadata"]
    assert data["metadata"]["retrieval_attempts"] == 2


@patch("src.graph.workflow.graph")
def test_post_query_returns_documents_retrieved(mock_graph, client):
    mock_graph.invoke.return_value = _mock_graph_result(
        raw_retrieval_results=[{"content": f"doc {i}"} for i in range(8)],
        merged_results=[{"content": f"doc {i}"} for i in range(6)],
    )

    response = client.post("/query", json={"query_text": "billing question"})
    assert response.status_code == 200
    data = response.json()
    assert "documents_retrieved" in data["metadata"]
    assert data["metadata"]["documents_retrieved"] == 8
    assert "documents_after_dedup" in data["metadata"]
    assert data["metadata"]["documents_after_dedup"] == 6


@patch("src.graph.workflow.graph")
def test_post_query_returns_retrieval_confidence(mock_graph, client):
    mock_graph.invoke.return_value = _mock_graph_result(retrieval_confidence_score=0.87)

    response = client.post("/query", json={"query_text": "billing question"})
    assert response.status_code == 200
    data = response.json()
    assert "retrieval_confidence" in data["metadata"]
    assert abs(data["metadata"]["retrieval_confidence"] - 0.87) < 0.001


@patch("src.graph.workflow.graph")
def test_post_query_citations_include_domain(mock_graph, client):
    mock_graph.invoke.return_value = _mock_graph_result(
        citations=[
            {
                "content": "Billing doc",
                "domain": "billing",
                "source": "payment-disputes.md",
                "score": 0.92,
                "doc_id": "d1",
                "chunk_text": "Billing doc",
                "title": "Payment Disputes",
                "source_file": "payment-disputes.md",
            },
            {
                "content": "Account doc",
                "domain": "account",
                "source": "login-procedures.md",
                "score": 0.89,
                "doc_id": "d2",
                "chunk_text": "Account doc",
                "title": "Login Procedures",
                "source_file": "login-procedures.md",
            },
        ]
    )

    response = client.post("/query", json={"query_text": "cross domain query"})
    assert response.status_code == 200
    data = response.json()
    citations = data["citations"]
    assert len(citations) == 2
    for citation in citations:
        assert "domain" in citation
        assert "score" in citation


@patch("src.graph.workflow.graph")
def test_post_query_response_schema(mock_graph, client):
    mock_graph.invoke.return_value = _mock_graph_result()

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
