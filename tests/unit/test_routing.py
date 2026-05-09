from src.graph.routing import route_query


def _make_state(domain):
    return {
        "query_id": "test-id",
        "query_text": "test query",
        "messages": [],
        "classified_domain": domain,
        "confidence_rationale": "test",
        "routed_to_agent": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "run-1",
        "log_events": [],
    }


def test_billing_routes_to_billing_agent():
    assert route_query(_make_state("billing")) == "billing_agent"


def test_technical_routes_to_technical_agent():
    assert route_query(_make_state("technical")) == "technical_agent"


def test_account_routes_to_account_agent():
    assert route_query(_make_state("account")) == "account_agent"


def test_unknown_routes_to_fallback():
    assert route_query(_make_state("unknown")) == "fallback_handler"


def test_none_domain_routes_to_fallback():
    state = _make_state(None)
    assert route_query(state) == "fallback_handler"


def test_all_valid_domains_have_routes():
    domains = ["billing", "technical", "account", "unknown"]
    expected = ["billing_agent", "technical_agent", "account_agent", "fallback_handler"]
    for domain, expected_node in zip(domains, expected):
        assert route_query(_make_state(domain)) == expected_node
