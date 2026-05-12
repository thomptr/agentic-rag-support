from unittest.mock import MagicMock, patch

_DEFAULT_MERGED_RESULTS = [
    {
        "content": "Customers may dispute charges within 30 days",
        "metadata": {"title": "payment-disputes", "source_file": "payment-disputes.md"},
        "score": 0.92,
        "domain": "billing",
        "source_query": "double charge",
    },
    {
        "content": "If your account is locked, verify your identity",
        "metadata": {"title": "login-procedures", "source_file": "login-procedures.md"},
        "score": 0.89,
        "domain": "account",
        "source_query": "account locked",
    },
]


def _make_state(merged_results=_DEFAULT_MERGED_RESULTS, retrieval_confidence=None):
    return {
        "query_id": "test-id",
        "query_text": "I was charged twice and my account is locked",
        "messages": [],
        "classified_domain": None,
        "classified_domains": ["billing", "account"],
        "confidence_rationale": None,
        "current_node": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "run-1",
        "log_events": [],
        "search_queries": [],
        "raw_retrieval_results": None,
        "merged_results": merged_results,
        "retrieval_confidence": retrieval_confidence
        or {
            "score": 0.9,
            "result_count": 2,
            "avg_similarity": 0.9,
            "should_retry": False,
            "reason": "ok",
        },
        "retrieval_attempt": 1,
        "max_retrieval_attempts": 3,
    }


class TestResponseGenerator:
    @patch("src.agents.response_generator.ChatOpenAI")
    def test_generates_grounded_response_with_citations(self, mock_cls):
        from src.agents.response_generator import response_generator

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "For duplicate charges, contact billing within 30 days. For locked accounts, verify identity."
        mock_llm.invoke.return_value = mock_response
        mock_cls.return_value = mock_llm

        state = _make_state()
        result = response_generator(state)

        assert result["response_text"] is not None
        assert len(result["response_text"]) > 0

    @patch("src.agents.response_generator.ChatOpenAI")
    def test_citations_include_domain_field(self, mock_cls):
        from src.agents.response_generator import response_generator

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Response text here"
        mock_llm.invoke.return_value = mock_response
        mock_cls.return_value = mock_llm

        state = _make_state()
        result = response_generator(state)

        citations = result.get("citations", [])
        assert len(citations) > 0
        for citation in citations:
            assert "domain" in citation

    @patch("src.agents.response_generator.ChatOpenAI")
    def test_citations_include_score_field(self, mock_cls):
        from src.agents.response_generator import response_generator

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Response text here"
        mock_llm.invoke.return_value = mock_response
        mock_cls.return_value = mock_llm

        state = _make_state()
        result = response_generator(state)

        citations = result.get("citations", [])
        assert len(citations) > 0
        for citation in citations:
            assert "score" in citation

    @patch("src.agents.response_generator.ChatOpenAI")
    def test_citations_include_source_field(self, mock_cls):
        from src.agents.response_generator import response_generator

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Response text here"
        mock_llm.invoke.return_value = mock_response
        mock_cls.return_value = mock_llm

        state = _make_state()
        result = response_generator(state)

        citations = result.get("citations", [])
        assert len(citations) > 0
        for citation in citations:
            assert "source" in citation

    @patch("src.agents.response_generator.ChatOpenAI")
    def test_no_citations_when_no_merged_results(self, mock_cls):
        from src.agents.response_generator import response_generator

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "I don't have enough information to answer this question."
        mock_llm.invoke.return_value = mock_response
        mock_cls.return_value = mock_llm

        state = _make_state(merged_results=[])
        result = response_generator(state)

        citations = result.get("citations", [])
        assert len(citations) == 0

    @patch("src.agents.response_generator.ChatOpenAI")
    def test_knowledge_gap_response_when_confidence_below_threshold(self, mock_cls):
        from src.agents.response_generator import response_generator

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "I don't have enough information in my knowledge base."
        mock_llm.invoke.return_value = mock_response
        mock_cls.return_value = mock_llm

        low_confidence = {
            "score": 0.2,
            "result_count": 1,
            "avg_similarity": 0.2,
            "should_retry": False,
            "reason": "max attempts reached",
        }
        state = _make_state(merged_results=[], retrieval_confidence=low_confidence)
        result = response_generator(state)

        assert result["response_text"] is not None
        citations = result.get("citations", [])
        assert len(citations) == 0
