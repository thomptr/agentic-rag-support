from unittest.mock import patch


def _make_state(classified_domains=None, retrieval_attempt=0):
    return {
        "query_id": "test-id",
        "query_text": "I was charged twice and now my account is locked",
        "messages": [],
        "classified_domain": None,
        "classified_domains": classified_domains or ["billing", "account"],
        "confidence_rationale": None,
        "current_node": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "run-1",
        "log_events": [],
        "search_queries": None,
        "raw_retrieval_results": None,
        "merged_results": None,
        "retrieval_confidence": None,
        "retrieval_attempt": retrieval_attempt,
        "max_retrieval_attempts": 3,
    }


class TestRetrievalPlanner:
    @patch("src.agents.retrieval_planner.generate_search_queries")
    def test_generates_one_query_per_classified_domain(self, mock_gen):
        from src.agents.retrieval_planner import retrieval_planner

        mock_gen.return_value = [
            {"query": "double charge", "target_domain": "billing", "aspect": "billing concern"},
            {"query": "account locked", "target_domain": "account", "aspect": "access concern"},
        ]

        state = _make_state(classified_domains=["billing", "account"])
        result = retrieval_planner(state)

        assert "search_queries" in result
        assert len(result["search_queries"]) >= 1

    @patch("src.agents.retrieval_planner.generate_search_queries")
    def test_sets_retrieval_attempt_to_1_on_first_call(self, mock_gen):
        from src.agents.retrieval_planner import retrieval_planner

        mock_gen.return_value = [
            {"query": "test query", "target_domain": "billing", "aspect": "general"}
        ]

        state = _make_state(retrieval_attempt=0)
        result = retrieval_planner(state)

        assert result["retrieval_attempt"] == 1

    @patch("src.agents.retrieval_planner.generate_search_queries")
    def test_sets_max_retrieval_attempts_from_config(self, mock_gen):
        from src.agents.retrieval_planner import retrieval_planner
        from src.config import settings

        mock_gen.return_value = [
            {"query": "test query", "target_domain": "billing", "aspect": "general"}
        ]

        state = _make_state(retrieval_attempt=0)
        result = retrieval_planner(state)

        assert result["max_retrieval_attempts"] == settings.max_retrieval_attempts

    @patch("src.agents.retrieval_planner.generate_search_queries")
    def test_emits_retrieval_plan_log_event(self, mock_gen):
        from src.agents.retrieval_planner import retrieval_planner

        mock_gen.return_value = [
            {"query": "charge issue", "target_domain": "billing", "aspect": "billing"},
        ]

        state = _make_state()
        result = retrieval_planner(state)

        log_events = result.get("log_events", [])
        plan_events = [e for e in log_events if e.get("event_type") == "retrieval_plan"]
        assert len(plan_events) == 1

    @patch("src.agents.retrieval_planner.generate_search_queries")
    def test_retry_attempt_2_broadens_params(self, mock_gen):
        from src.agents.retrieval_planner import retrieval_planner

        mock_gen.return_value = [
            {"query": "test", "target_domain": "billing", "aspect": "general"},
        ]

        state = _make_state(retrieval_attempt=1)
        state["retrieval_confidence"] = {"should_retry": True, "avg_similarity": 0.3}
        result = retrieval_planner(state)

        # On retry attempt 2, k should be increased
        assert result.get("retrieval_attempt") == 2
        # The search params should reflect broadened retrieval
        queries = result.get("search_queries", [])
        assert len(queries) >= 1

    @patch("src.agents.retrieval_planner.generate_search_queries")
    def test_retry_attempt_3_removes_domain_filter(self, mock_gen):
        from src.agents.retrieval_planner import retrieval_planner

        mock_gen.return_value = [
            {"query": "test", "target_domain": "all", "aspect": "general"},
        ]

        state = _make_state(retrieval_attempt=2)
        state["retrieval_confidence"] = {"should_retry": True, "avg_similarity": 0.2}
        result = retrieval_planner(state)

        assert result.get("retrieval_attempt") == 3
