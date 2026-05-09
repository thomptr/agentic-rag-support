from src.observability.logger import (
    log_agent_response,
    log_llm_call,
    log_retrieval,
    log_routing_decision,
)


def test_log_llm_call_shape():
    event = log_llm_call(
        run_id="run-1",
        agent="supervisor",
        model="claude-3",
        prompt_hash="abc123",
        input_tokens=100,
        output_tokens=50,
        latency_ms=200.0,
    )
    assert event["event_type"] == "llm_call"
    assert event["run_id"] == "run-1"
    assert event["agent"] == "supervisor"
    assert event["model"] == "claude-3"
    assert event["prompt_hash"] == "abc123"
    assert event["input_tokens"] == 100
    assert event["output_tokens"] == 50
    assert event["latency_ms"] == 200.0


def test_log_retrieval_shape():
    results = [{"doc_id": "d1", "score": 0.9, "preview": "sample text"}]
    event = log_retrieval(
        run_id="run-1",
        agent="billing_agent",
        query="refund policy",
        top_k=5,
        results=results,
        elapsed_ms=50.0,
    )
    assert event["event_type"] == "retrieval"
    assert event["run_id"] == "run-1"
    assert event["agent"] == "billing_agent"
    assert event["query"] == "refund policy"
    assert event["top_k"] == 5
    assert event["results"] == results
    assert event["elapsed_ms"] == 50.0


def test_log_routing_decision_shape():
    event = log_routing_decision(
        run_id="run-1",
        query_text="why was I charged?",
        classified_domain="billing",
        confidence_rationale="mentions charges",
        routed_to="billing_agent",
    )
    assert event["event_type"] == "routing_decision"
    assert event["run_id"] == "run-1"
    assert event["classified_domain"] == "billing"
    assert event["confidence_rationale"] == "mentions charges"
    assert event["routed_to"] == "billing_agent"


def test_log_agent_response_shape():
    event = log_agent_response(
        run_id="run-1",
        agent="billing_agent",
        response_length=250,
        citation_count=3,
    )
    assert event["event_type"] == "agent_response"
    assert event["run_id"] == "run-1"
    assert event["agent"] == "billing_agent"
    assert event["response_length"] == 250
    assert event["citation_count"] == 3


def test_log_llm_call_returns_dict():
    result = log_llm_call(
        run_id="r",
        agent="a",
        model="m",
        prompt_hash="h",
        input_tokens=1,
        output_tokens=1,
        latency_ms=1.0,
    )
    assert isinstance(result, dict)


def test_log_retrieval_returns_dict():
    result = log_retrieval(run_id="r", agent="a", query="q", top_k=5, results=[], elapsed_ms=10.0)
    assert isinstance(result, dict)


def test_log_routing_decision_returns_dict():
    result = log_routing_decision(
        run_id="r",
        query_text="q",
        classified_domain="billing",
        confidence_rationale="x",
        routed_to="y",
    )
    assert isinstance(result, dict)


def test_log_agent_response_returns_dict():
    result = log_agent_response(run_id="r", agent="a", response_length=100, citation_count=2)
    assert isinstance(result, dict)
