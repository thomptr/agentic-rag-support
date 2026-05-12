def _make_state(merged_results=None, retrieval_attempt=1, max_retrieval_attempts=3):
    return {
        "query_id": "test-id",
        "query_text": "test query",
        "messages": [],
        "classified_domain": None,
        "classified_domains": ["billing"],
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
        "retrieval_confidence": None,
        "retrieval_attempt": retrieval_attempt,
        "max_retrieval_attempts": max_retrieval_attempts,
    }


def _make_high_conf_docs(count=5, score=0.85):
    return [{"content": f"doc {i}", "score": score, "domain": "billing"} for i in range(count)]


def _make_low_conf_docs(count=1, score=0.3):
    return [{"content": f"doc {i}", "score": score, "domain": "billing"} for i in range(count)]


class TestConfidenceCheck:
    def test_retry_on_low_avg_similarity(self):
        from src.agents.confidence_check import confidence_check

        state = _make_state(merged_results=_make_low_conf_docs(5, score=0.2))
        command = confidence_check(state)

        assert command.goto == "retrieval_planner"
        assert command.update["retrieval_confidence"]["should_retry"] is True

    def test_retry_on_low_result_count(self):
        from src.agents.confidence_check import confidence_check

        # Only 1 result, below MIN_RESULT_COUNT=3
        state = _make_state(merged_results=_make_high_conf_docs(1, score=0.9))
        command = confidence_check(state)

        assert command.goto == "retrieval_planner"

    def test_proceed_on_high_confidence_dispatches_to_domain_agent(self):
        """High confidence + classified_domains=['billing'] → billing_agent.

        Post-refactor confidence_check dispatches to the domain-specific agent
        rather than the generic response_generator. _make_state defaults to
        classified_domains=['billing'].
        """
        from src.agents.confidence_check import confidence_check

        state = _make_state(merged_results=_make_high_conf_docs(5, score=0.85))
        command = confidence_check(state)

        assert command.goto == "billing_agent"
        assert command.update["retrieval_confidence"]["should_retry"] is False

    def test_stop_after_max_retrieval_attempts(self):
        from src.agents.confidence_check import confidence_check
        from src.config import settings

        # Even with low confidence, should not retry at max attempts.
        state = _make_state(
            merged_results=_make_low_conf_docs(1, score=0.1),
            retrieval_attempt=settings.max_retrieval_attempts,
        )
        command = confidence_check(state)

        # Proceed to the domain agent (billing per _make_state default) even
        # though confidence is low — the retry budget is exhausted.
        assert command.goto == "billing_agent"

    def test_emits_confidence_assessment_log_event(self):
        from src.agents.confidence_check import confidence_check

        state = _make_state(merged_results=_make_high_conf_docs(5))
        command = confidence_check(state)

        log_events = command.update.get("log_events", [])
        confidence_events = [
            e for e in log_events if e.get("event_type") == "confidence_assessment"
        ]
        assert len(confidence_events) == 1

    def test_emits_retry_log_event_on_retry(self):
        from src.agents.confidence_check import confidence_check

        state = _make_state(merged_results=_make_low_conf_docs(1, score=0.2))
        command = confidence_check(state)

        if command.goto == "retrieval_planner":
            log_events = command.update.get("log_events", [])
            retry_events = [e for e in log_events if e.get("event_type") == "retrieval_retry"]
            assert len(retry_events) >= 1

    def test_empty_merged_results_triggers_retry(self):
        from src.agents.confidence_check import confidence_check

        state = _make_state(merged_results=[])
        command = confidence_check(state)

        # Empty results at attempt 1 should retry
        assert command.goto == "retrieval_planner"

    def test_confidence_check_writes_retrieval_confidence_to_state(self):
        from src.agents.confidence_check import confidence_check

        state = _make_state(merged_results=_make_high_conf_docs(5))
        command = confidence_check(state)

        update = command.update
        assert "retrieval_confidence" in update
        conf = update["retrieval_confidence"]
        assert "score" in conf
        assert "result_count" in conf
        assert "should_retry" in conf
