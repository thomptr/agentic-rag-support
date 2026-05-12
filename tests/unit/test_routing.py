from src.graph.routing import route_confidence_check, route_supervisor


def _make_state_with_domains(domains=None, confidence=None, retrieval_attempt=1):
    return {
        "query_id": "test-id",
        "query_text": "test query",
        "messages": [],
        "classified_domain": (domains or ["unknown"])[0] if domains else "unknown",
        "classified_domains": domains,
        "confidence_rationale": "test",
        "current_node": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "run-1",
        "log_events": [],
        "search_queries": None,
        "raw_retrieval_results": None,
        "merged_results": None,
        "retrieval_confidence": confidence,
        "retrieval_attempt": retrieval_attempt,
        "max_retrieval_attempts": 3,
    }


class TestRouteSupervisor:
    def test_billing_routes_to_security_check(self):
        state = _make_state_with_domains(["billing"])
        assert route_supervisor(state) == "security_check"

    def test_technical_routes_to_security_check(self):
        state = _make_state_with_domains(["technical"])
        assert route_supervisor(state) == "security_check"

    def test_account_routes_to_security_check(self):
        state = _make_state_with_domains(["account"])
        assert route_supervisor(state) == "security_check"

    def test_unknown_routes_to_fallback(self):
        state = _make_state_with_domains(["unknown"])
        assert route_supervisor(state) == "fallback_handler"

    def test_none_domains_routes_to_fallback(self):
        state = _make_state_with_domains(None)
        assert route_supervisor(state) == "fallback_handler"

    def test_multi_domain_routes_to_security_check(self):
        state = _make_state_with_domains(["billing", "account"])
        assert route_supervisor(state) == "security_check"

    def test_empty_domains_routes_to_fallback(self):
        state = _make_state_with_domains([])
        assert route_supervisor(state) == "fallback_handler"


class TestRouteConfidenceCheck:
    def test_should_retry_routes_to_security_check(self):
        confidence = {"should_retry": True, "score": 0.3, "reason": "low similarity"}
        state = _make_state_with_domains(["billing"], confidence=confidence)
        assert route_confidence_check(state) == "retrieval_planner"

    def test_sufficient_confidence_routes_to_domain_agent(self):
        """billing domain → billing_agent (was response_generator pre-refactor)."""
        confidence = {"should_retry": False, "score": 0.85, "reason": "sufficient"}
        state = _make_state_with_domains(["billing"], confidence=confidence)
        assert route_confidence_check(state) == "billing_agent"

    def test_no_confidence_defaults_to_domain_agent(self):
        state = _make_state_with_domains(["technical"], confidence=None)
        assert route_confidence_check(state) == "technical_agent"

    def test_unknown_domain_falls_back_to_generic_response_generator(self):
        state = _make_state_with_domains([], confidence=None)
        assert route_confidence_check(state) == "response_generator"
