import pytest

from src.rag.retriever import retrieve_documents

pytestmark = pytest.mark.integration


def test_retriever_returns_results():
    docs = retrieve_documents(
        query="pricing plans",
        domain="billing",
        run_id="test-run-001",
        agent="test",
    )
    assert isinstance(docs, list)
    assert len(docs) > 0
    assert "content" in docs[0]
    assert "score" in docs[0]
    assert "metadata" in docs[0]


def test_retriever_respects_domain_filter():
    billing_docs = retrieve_documents(
        query="pricing",
        domain="billing",
        run_id="test-run-002",
        agent="test",
    )
    for doc in billing_docs:
        assert doc["metadata"]["domain"] == "billing"


def test_retriever_technical_domain():
    docs = retrieve_documents(
        query="API key authentication",
        domain="technical",
        run_id="test-run-003",
        agent="test",
    )
    assert isinstance(docs, list)
    for doc in docs:
        assert doc["metadata"]["domain"] == "technical"


def test_retriever_returns_scores():
    docs = retrieve_documents(
        query="refund eligibility",
        domain="billing",
        run_id="test-run-004",
        agent="test",
    )
    if docs:
        assert all(isinstance(d["score"], float) for d in docs)
        assert all(d["score"] >= 0.0 for d in docs)


def test_retriever_handles_empty_results_gracefully(monkeypatch):
    from src.db import connection

    class MockVS:
        def similarity_search_with_relevance_scores(self, q, k, filter):
            return []

    monkeypatch.setattr(connection, "get_vector_store", lambda: MockVS())

    import importlib

    from src.rag import retriever as retriever_module

    importlib.reload(retriever_module)

    docs = retriever_module.retrieve_documents(
        query="nothing here",
        domain="billing",
        run_id="test-run-005",
        agent="test",
    )
    assert docs == []
