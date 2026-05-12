from src.agents.fallback import fallback_handler


def _make_state(query_text="random query"):
    return {
        "query_id": "test-id",
        "query_text": query_text,
        "messages": [],
        "classified_domain": "unknown",
        "confidence_rationale": "Cannot classify",
        "current_node": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "run-1",
        "log_events": [],
    }


def test_fallback_returns_acknowledgement():
    state = _make_state("some ambiguous query")
    result = fallback_handler(state)
    assert result["response_text"] is not None
    assert len(result["response_text"]) > 0


def test_fallback_includes_original_query_in_response():
    query = "something very specific and unusual"
    state = _make_state(query)
    result = fallback_handler(state)
    assert query in result["response_text"]


def test_fallback_returns_empty_citations():
    state = _make_state()
    result = fallback_handler(state)
    assert result["citations"] == []


def test_fallback_emits_agent_response_event():
    state = _make_state()
    result = fallback_handler(state)
    log_events = result.get("log_events", [])
    event_types = [e.get("event_type") for e in log_events]
    assert "agent_response" in event_types


def test_fallback_response_mentions_inability_to_route():
    state = _make_state("some query")
    result = fallback_handler(state)
    response = result["response_text"].lower()
    # Response should communicate routing failure, not a generic error
    assert any(word in response for word in ("route", "route", "categor", "topic", "support team"))


def test_fallback_handles_empty_query():
    state = _make_state("")
    result = fallback_handler(state)
    assert result["response_text"] is not None
    assert result["citations"] == []
