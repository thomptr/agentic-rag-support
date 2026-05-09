from unittest.mock import MagicMock, patch

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


def test_retriever_respects_domain_filter():
    billing_docs = retrieve_documents(
        query="pricing",
        domain="billing",
        run_id="test-run-002",
        agent="test",
    )
    for doc in billing_docs:
        assert doc["metadata"]["domain"] == "billing"


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


# --- Multi-domain retrieval tests (T044) ---


class TestMultiDomainRetrieval:
    @patch("src.rag.retriever.get_vector_store")
    def test_multi_domain_filter_uses_in_operator(self, mock_get_vs):
        from src.rag.retriever import retrieve_documents_multi_domain

        mock_vs = MagicMock()
        mock_vs.similarity_search_with_relevance_scores.return_value = []
        mock_get_vs.return_value = mock_vs

        retrieve_documents_multi_domain(
            query="test query",
            domains=["billing", "account"],
            run_id="test-run",
            k=5,
        )

        call_kwargs = mock_vs.similarity_search_with_relevance_scores.call_args
        filter_arg = call_kwargs.kwargs.get("filter", {})
        assert filter_arg is not None
        # Multi-domain: should use $in
        assert "$in" in filter_arg.get("domain", {}) or isinstance(filter_arg.get("domain"), dict)

    @patch("src.rag.retriever.get_vector_store")
    def test_single_domain_uses_direct_filter(self, mock_get_vs):
        from src.rag.retriever import retrieve_documents_multi_domain

        mock_vs = MagicMock()
        mock_vs.similarity_search_with_relevance_scores.return_value = []
        mock_get_vs.return_value = mock_vs

        retrieve_documents_multi_domain(
            query="billing query",
            domains=["billing"],
            run_id="test-run",
            k=5,
        )

        call_kwargs = mock_vs.similarity_search_with_relevance_scores.call_args
        filter_arg = call_kwargs.kwargs.get("filter", {})
        # Single domain — should use simple {"domain": "billing"} not $in
        assert filter_arg.get("domain") == "billing"

    @patch("src.rag.retriever.get_vector_store")
    def test_unfiltered_retrieval_has_no_domain_filter(self, mock_get_vs):
        from src.rag.retriever import retrieve_documents_unfiltered

        mock_vs = MagicMock()
        mock_vs.similarity_search_with_relevance_scores.return_value = []
        mock_get_vs.return_value = mock_vs

        retrieve_documents_unfiltered(query="test query", run_id="test-run", k=15)

        call_kwargs = mock_vs.similarity_search_with_relevance_scores.call_args
        # Should call without a filter keyword argument
        filter_arg = call_kwargs.kwargs.get("filter", None)
        assert filter_arg is None

    @patch("src.rag.retriever.get_vector_store")
    def test_retriever_returns_domain_and_source_query(self, mock_get_vs):
        from src.rag.retriever import retrieve_documents_multi_domain

        mock_doc = MagicMock()
        mock_doc.page_content = "billing content"
        mock_doc.metadata = {"domain": "billing", "source_file": "pricing-plans.md"}

        mock_vs = MagicMock()
        mock_vs.similarity_search_with_relevance_scores.return_value = [(mock_doc, 0.9)]
        mock_get_vs.return_value = mock_vs

        results = retrieve_documents_multi_domain(
            query="billing query",
            domains=["billing"],
            run_id="test-run",
            k=5,
        )

        assert len(results) == 1
        assert results[0]["domain"] == "billing"
        assert results[0]["source_query"] == "billing query"
        assert results[0]["score"] == 0.9

    @patch("src.rag.retriever.get_vector_store")
    def test_retriever_handles_exception_gracefully(self, mock_get_vs):
        from src.rag.retriever import retrieve_documents_multi_domain

        mock_vs = MagicMock()
        mock_vs.similarity_search_with_relevance_scores.side_effect = Exception("DB error")
        mock_get_vs.return_value = mock_vs

        results = retrieve_documents_multi_domain(
            query="test", domains=["billing"], run_id="test", k=5
        )
        assert results == []


class TestMultiQueryRecall:
    def test_combined_results_cover_more_documents_than_single_query(self):
        from src.rag.result_merger import merge_results

        billing_docs = [
            {
                "content": f"billing content {i}",
                "score": 0.85 - i * 0.05,
                "domain": "billing",
                "source_query": "q1",
            }
            for i in range(3)
        ]
        account_docs = [
            {
                "content": f"account content {i}",
                "score": 0.80 - i * 0.05,
                "domain": "account",
                "source_query": "q2",
            }
            for i in range(3)
        ]

        all_results = billing_docs + account_docs
        merged = merge_results(all_results)

        assert len(merged) == 6

    def test_dedup_removes_overlapping_results(self):
        from src.rag.result_merger import merge_results

        shared_content = "shared document content about billing"
        doc_from_q1 = {
            "content": shared_content,
            "score": 0.9,
            "domain": "billing",
            "source_query": "q1",
        }
        doc_from_q2 = {
            "content": shared_content,
            "score": 0.85,
            "domain": "billing",
            "source_query": "q2",
        }
        unique_q2 = {
            "content": "unique to q2",
            "score": 0.8,
            "domain": "account",
            "source_query": "q2",
        }

        merged = merge_results([doc_from_q1, doc_from_q2, unique_q2])
        assert len(merged) == 2
