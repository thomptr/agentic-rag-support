from unittest.mock import patch


def _make_state(search_queries=None, retrieval_attempt=1):
    return {
        "query_id": "test-id",
        "query_text": "I was charged twice and my account is locked",
        "messages": [],
        "classified_domain": None,
        "classified_domains": ["billing", "account"],
        "confidence_rationale": None,
        "routed_to_agent": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "run-1",
        "log_events": [],
        "search_queries": search_queries
        or [
            {"query": "double charge", "target_domain": "billing", "aspect": "billing"},
            {"query": "account locked", "target_domain": "account", "aspect": "access"},
        ],
        "raw_retrieval_results": None,
        "merged_results": None,
        "retrieval_confidence": None,
        "retrieval_attempt": retrieval_attempt,
        "max_retrieval_attempts": 3,
    }


class TestMultiRetriever:
    @patch("src.agents.multi_retriever.retrieve_documents_multi_domain")
    @patch("src.agents.multi_retriever.merge_results")
    def test_executes_queries_and_collects_results(self, mock_merge, mock_retrieve):
        from src.agents.multi_retriever import multi_retriever

        mock_retrieve.return_value = [
            {"content": "billing doc", "score": 0.9, "domain": "billing", "source_query": "test"}
        ]
        mock_merge.return_value = [
            {"content": "billing doc", "score": 0.9, "domain": "billing", "source_query": "test"}
        ]

        state = _make_state()
        result = multi_retriever(state)

        assert mock_retrieve.called
        assert "merged_results" in result

    @patch("src.agents.multi_retriever.retrieve_documents_multi_domain")
    @patch("src.agents.multi_retriever.merge_results")
    def test_populates_merged_results(self, mock_merge, mock_retrieve):
        from src.agents.multi_retriever import multi_retriever

        docs = [
            {"content": "billing doc", "score": 0.9, "domain": "billing", "source_query": "q1"},
            {"content": "account doc", "score": 0.85, "domain": "account", "source_query": "q2"},
        ]
        mock_retrieve.return_value = docs
        mock_merge.return_value = docs

        state = _make_state()
        result = multi_retriever(state)

        assert result["merged_results"] is not None
        assert len(result["merged_results"]) > 0

    @patch("src.agents.multi_retriever.retrieve_documents_multi_domain")
    @patch("src.agents.multi_retriever.merge_results")
    def test_calls_result_merger(self, mock_merge, mock_retrieve):
        from src.agents.multi_retriever import multi_retriever

        mock_retrieve.return_value = []
        mock_merge.return_value = []

        state = _make_state()
        multi_retriever(state)

        assert mock_merge.called

    @patch("src.agents.multi_retriever.retrieve_documents_multi_domain")
    @patch("src.agents.multi_retriever.merge_results")
    def test_populates_retrieved_documents(self, mock_merge, mock_retrieve):
        from src.agents.multi_retriever import multi_retriever

        docs = [{"content": "doc", "score": 0.8, "domain": "billing", "source_query": "q"}]
        mock_retrieve.return_value = docs
        mock_merge.return_value = docs

        state = _make_state()
        result = multi_retriever(state)

        assert result.get("retrieved_documents") is not None

    @patch("src.agents.multi_retriever.retrieve_documents_multi_domain")
    @patch("src.agents.multi_retriever.merge_results")
    def test_emits_multi_retrieval_log_event(self, mock_merge, mock_retrieve):
        from src.agents.multi_retriever import multi_retriever

        mock_retrieve.return_value = []
        mock_merge.return_value = []

        state = _make_state()
        result = multi_retriever(state)

        log_events = result.get("log_events", [])
        retrieval_events = [e for e in log_events if e.get("event_type") == "multi_retrieval"]
        assert len(retrieval_events) == 1
