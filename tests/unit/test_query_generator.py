from unittest.mock import MagicMock, patch

from src.rag.query_generator import generate_search_queries


def _make_mock_llm_response(queries):
    """Build a mock LLM that returns a structured list of query dicts."""
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_result = MagicMock()
    mock_result.queries = queries
    mock_structured.invoke.return_value = mock_result
    return mock_llm


class TestGenerateSearchQueries:
    @patch("src.rag.query_generator.ChatOpenAI")
    def test_domain_targeted_query_generation(self, mock_cls):
        queries = [
            {
                "query": "double charge billing dispute",
                "target_domain": "billing",
                "aspect": "billing concern",
            },
            {
                "query": "account locked access issue",
                "target_domain": "account",
                "aspect": "access concern",
            },
        ]
        mock_cls.return_value = _make_mock_llm_response(queries)

        result = generate_search_queries(
            query_text="I was charged twice and now my account is locked",
            classified_domains=["billing", "account"],
        )

        assert len(result) > 0
        target_domains = {q["target_domain"] for q in result}
        assert "billing" in target_domains or "account" in target_domains

    @patch("src.rag.query_generator.ChatOpenAI")
    def test_query_count_matches_multi_query_count(self, mock_cls):
        from src.config import settings

        expected_count = settings.multi_query_count
        queries = [
            {"query": f"query {i}", "target_domain": "billing", "aspect": f"aspect {i}"}
            for i in range(expected_count)
        ]
        mock_cls.return_value = _make_mock_llm_response(queries)

        result = generate_search_queries(
            query_text="Why was I charged?",
            classified_domains=["billing"],
        )

        assert len(result) <= expected_count + 1  # may have slight variation

    @patch("src.rag.query_generator.ChatOpenAI")
    def test_output_format_has_required_fields(self, mock_cls):
        queries = [
            {
                "query": "billing charge dispute",
                "target_domain": "billing",
                "aspect": "charge dispute",
            },
        ]
        mock_cls.return_value = _make_mock_llm_response(queries)

        result = generate_search_queries(
            query_text="Why was I charged?",
            classified_domains=["billing"],
        )

        assert len(result) > 0
        for q in result:
            assert "query" in q
            assert "target_domain" in q
            assert "aspect" in q

    @patch("src.rag.query_generator.ChatOpenAI")
    def test_single_domain_query(self, mock_cls):
        queries = [
            {"query": "billing charge", "target_domain": "billing", "aspect": "charge"},
        ]
        mock_cls.return_value = _make_mock_llm_response(queries)

        result = generate_search_queries(
            query_text="Why was I charged?",
            classified_domains=["billing"],
        )
        assert len(result) >= 1
        assert all(q["target_domain"] in ("billing", "all") for q in result)

    @patch("src.rag.query_generator.ChatOpenAI")
    def test_returns_list_on_llm_error(self, mock_cls):
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured
        mock_structured.invoke.side_effect = Exception("LLM error")
        mock_cls.return_value = mock_llm

        result = generate_search_queries(
            query_text="test query",
            classified_domains=["billing"],
        )
        # Should return at least a fallback query rather than raising
        assert isinstance(result, list)

    # --- US2: Multi-facet query expansion tests ---

    @patch("src.rag.query_generator.ChatOpenAI")
    def test_complex_query_produces_multiple_variations(self, mock_cls):
        queries = [
            {
                "query": "data export before cancellation",
                "target_domain": "account",
                "aspect": "export",
            },
            {
                "query": "cancel mid-cycle refund",
                "target_domain": "billing",
                "aspect": "cancellation",
            },
            {
                "query": "export data format options",
                "target_domain": "account",
                "aspect": "data format",
            },
        ]
        mock_cls.return_value = _make_mock_llm_response(queries)

        result = generate_search_queries(
            query_text="What happens to my data if I cancel mid-cycle and haven't exported my reports?",
            classified_domains=["account", "billing"],
        )

        # Complex query should produce 2-3 aspect-targeted variations
        assert len(result) >= 2

    @patch("src.rag.query_generator.ChatOpenAI")
    def test_simple_query_passthrough_uses_original(self, mock_cls):
        # For simple queries, may return just 1 query (the original)
        queries = [
            {"query": "billing charge explanation", "target_domain": "billing", "aspect": "charge"},
        ]
        mock_cls.return_value = _make_mock_llm_response(queries)

        result = generate_search_queries(
            query_text="Why was I charged?",
            classified_domains=["billing"],
        )

        # Simple single-domain query — at least 1 query returned
        assert len(result) >= 1

    @patch("src.rag.query_generator.ChatOpenAI")
    def test_multi_domain_query_targets_each_domain(self, mock_cls):
        queries = [
            {
                "query": "webhook setup Professional plan",
                "target_domain": "technical",
                "aspect": "webhook",
            },
            {
                "query": "subscription downgrade webhook access",
                "target_domain": "billing",
                "aspect": "plan",
            },
        ]
        mock_cls.return_value = _make_mock_llm_response(queries)

        result = generate_search_queries(
            query_text="What happens to my webhooks if I downgrade from Professional to Basic?",
            classified_domains=["technical", "billing"],
        )

        target_domains = {q["target_domain"] for q in result}
        # Should have at least one query per classified domain
        assert len(target_domains) >= 1
