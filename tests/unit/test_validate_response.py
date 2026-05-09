from src.agents.validate_response import validate_response


def _make_state(response_text=None, citations=None, retrieved_docs=None):
    return {
        "query_id": "test-id",
        "query_text": "test query",
        "messages": [],
        "classified_domain": "billing",
        "confidence_rationale": "test",
        "routed_to_agent": "billing_agent",
        "retrieved_documents": retrieved_docs,
        "response_text": response_text,
        "citations": citations,
        "run_id": "run-1",
        "log_events": [],
    }


def test_valid_response_passes():
    state = _make_state(
        response_text="Your charge is explained by our pricing plan.",
        citations=[{"doc_id": "d1", "chunk_text": "pricing plan text", "score": 0.9}],
    )
    result = validate_response(state)
    assert "log_events" in result


def test_empty_citations_are_flagged():
    state = _make_state(
        response_text="Some response",
        citations=[],
    )
    result = validate_response(state)
    log_events = result.get("log_events", [])
    validation_events = [e for e in log_events if e.get("event_type") == "validation"]
    assert len(validation_events) > 0
    assert validation_events[0].get("citations_valid") is False


def test_none_citations_are_flagged():
    state = _make_state(
        response_text="Some response",
        citations=None,
    )
    result = validate_response(state)
    log_events = result.get("log_events", [])
    validation_events = [e for e in log_events if e.get("event_type") == "validation"]
    assert len(validation_events) > 0
    assert validation_events[0].get("citations_valid") is False


def test_empty_response_text_is_flagged():
    state = _make_state(
        response_text="",
        citations=[{"doc_id": "d1", "chunk_text": "text", "score": 0.9}],
    )
    result = validate_response(state)
    log_events = result.get("log_events", [])
    validation_events = [e for e in log_events if e.get("event_type") == "validation"]
    assert len(validation_events) > 0
    assert validation_events[0].get("response_valid") is False


def test_low_confidence_retrieval_annotated():
    state = _make_state(
        response_text="Here is your answer.",
        citations=[{"doc_id": "d1", "chunk_text": "text", "score": 0.1}],
        retrieved_docs=[{"content": "text", "metadata": {}, "score": 0.1}],
    )
    result = validate_response(state)
    log_events = result.get("log_events", [])
    validation_events = [e for e in log_events if e.get("event_type") == "validation"]
    assert len(validation_events) > 0
    # Low confidence should be noted
    event = validation_events[0]
    assert "low_confidence" in event or event.get("avg_score", 1.0) < 0.5
