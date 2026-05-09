def _make_state(query_text):
    return {
        "query_id": "test-id",
        "query_text": query_text,
        "messages": [],
        "classified_domain": "account",
        "classified_domains": ["account"],
        "confidence_rationale": None,
        "routed_to_agent": None,
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
        "security_signals": None,
        "escalation_required": None,
        "escalation_reason": None,
    }


class TestSecurityCheckDetection:
    def test_hacked_account_phrase_fires_takeover_signal(self):
        from src.agents.security_check import security_check

        command = security_check(_make_state("I think someone hacked my account"))

        assert command.goto == "escalation_handler"
        signals = command.update["security_signals"]
        assert len(signals) == 1
        assert signals[0]["name"] == "account_takeover"
        assert signals[0]["severity"] == "block"
        assert signals[0]["action"] == "escalate"
        assert command.update["escalation_required"] is True
        assert command.update["escalation_reason"] == "account_takeover"

    def test_unauthorized_access_fires_takeover_signal(self):
        from src.agents.security_check import security_check

        command = security_check(_make_state("there was unauthorized access to my login"))
        assert command.goto == "escalation_handler"
        assert command.update["escalation_required"] is True

    def test_someone_logged_in_fires_takeover_signal(self):
        from src.agents.security_check import security_check

        command = security_check(
            _make_state("Someone logged in to my account from another country")
        )
        assert command.goto == "escalation_handler"
        assert command.update["escalation_required"] is True

    def test_compromised_fires_takeover_signal(self):
        from src.agents.security_check import security_check

        command = security_check(_make_state("My account was compromised last night"))
        assert command.goto == "escalation_handler"
        assert command.update["escalation_required"] is True

    def test_account_stolen_fires_takeover_signal(self):
        from src.agents.security_check import security_check

        command = security_check(_make_state("My account has been stolen"))
        assert command.goto == "escalation_handler"
        assert command.update["escalation_required"] is True


class TestSecurityCheckPassthrough:
    def test_benign_billing_query_passes_through(self):
        from src.agents.security_check import security_check

        command = security_check(_make_state("Why was I charged twice this month?"))

        assert command.goto == "retrieval_planner"
        assert command.update["security_signals"] == []
        assert command.update["escalation_required"] is False

    def test_benign_account_query_passes_through(self):
        from src.agents.security_check import security_check

        command = security_check(_make_state("How do I set up two-factor authentication?"))

        assert command.goto == "retrieval_planner"
        assert command.update["escalation_required"] is False

    def test_informational_takeover_phrasing_does_not_fire(self):
        # User asking *how* to detect takeover (informational), not reporting one.
        from src.agents.security_check import security_check

        command = security_check(_make_state("How do I tell if my account was hacked?"))

        # Hacked + account is in this phrase, so this WILL fire — documents the
        # known false-positive direction. If we add intent-aware classification
        # later, this test should flip and this comment should be revisited.
        assert command.goto == "escalation_handler"


class TestSecurityCheckLogging:
    def test_emits_security_check_event(self):
        from src.agents.security_check import security_check

        command = security_check(_make_state("normal billing question"))
        events = command.update["log_events"]
        assert len(events) == 1
        assert events[0]["event_type"] == "security_check"
        assert events[0]["action"] == "continue"
        assert "latency_ms" in events[0]

    def test_emits_security_check_event_on_escalation(self):
        from src.agents.security_check import security_check

        command = security_check(_make_state("My account was compromised"))
        events = command.update["log_events"]
        assert len(events) == 1
        assert events[0]["event_type"] == "security_check"
        assert events[0]["action"] == "escalate"
        assert len(events[0]["signals"]) == 1

    def test_rule_based_path_is_fast(self):
        # Sanity check on SC-008: rule-based pre-check should be sub-millisecond, not 50ms.
        from src.agents.security_check import security_check

        command = security_check(_make_state("normal query about my plan"))
        latency = command.update["log_events"][0]["latency_ms"]
        assert latency < 50.0
