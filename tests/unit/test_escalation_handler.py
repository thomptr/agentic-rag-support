def _make_state(signals=None, reason="account_takeover"):
    return {
        "query_id": "test-id",
        "query_text": "I think someone hacked my account",
        "messages": [],
        "classified_domain": "account",
        "classified_domains": ["account"],
        "confidence_rationale": None,
        "routed_to_agent": "escalation_handler",
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "run-1",
        "log_events": [],
        "search_queries": None,
        "raw_retrieval_results": None,
        "merged_results": None,
        "retrieval_confidence": None,
        "retrieval_attempt": 0,
        "max_retrieval_attempts": 3,
        "security_signals": signals
        if signals is not None
        else [
            {
                "name": "account_takeover",
                "matched_pattern": "hacked my account",
                "severity": "block",
                "action": "escalate",
            }
        ],
        "escalation_required": True,
        "escalation_reason": reason,
    }


class TestEscalationHandler:
    def test_returns_security_team_routing_response(self):
        from src.agents.escalation_handler import escalation_handler

        result = escalation_handler(_make_state())

        assert "security team" in result["response_text"].lower()
        assert result["citations"] == []
        assert result["routed_to_agent"] == "escalation_handler"

    def test_emits_escalation_triggered_event(self):
        from src.agents.escalation_handler import escalation_handler

        result = escalation_handler(_make_state())
        events = result["log_events"]

        escalation_events = [e for e in events if e["event_type"] == "escalation_triggered"]
        assert len(escalation_events) == 1
        assert escalation_events[0]["signal_name"] == "account_takeover"
        assert escalation_events[0]["matched_pattern"] == "hacked my account"
        assert escalation_events[0]["agent"] == "escalation_handler"

    def test_emits_agent_response_event(self):
        from src.agents.escalation_handler import escalation_handler

        result = escalation_handler(_make_state())
        events = result["log_events"]

        response_events = [e for e in events if e["event_type"] == "agent_response"]
        assert len(response_events) == 1
        assert response_events[0]["citation_count"] == 0

    def test_handles_missing_signals_gracefully(self):
        # Defensive: if escalation is required but no signals are populated, still produce
        # a sensible response and log event.
        from src.agents.escalation_handler import escalation_handler

        result = escalation_handler(_make_state(signals=[], reason="policy_violation"))

        assert result["response_text"]
        events = [e for e in result["log_events"] if e["event_type"] == "escalation_triggered"]
        assert events[0]["signal_name"] == "policy_violation"
