from src.observability.logger import (
    log_agent_response,
    log_confidence_assessment,
    log_knowledge_gap,
    log_llm_call,
    log_multi_retrieval,
    log_retrieval,
    log_retrieval_plan,
    log_retrieval_retry,
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


# --- New 002 event helpers ---


def test_log_retrieval_plan_shape():
    event = log_retrieval_plan(
        run_id="run-1",
        classified_domains=["billing", "account"],
        search_queries=[
            {"query": "double charge", "target_domain": "billing", "aspect": "billing"},
            {"query": "account locked", "target_domain": "account", "aspect": "account"},
        ],
        query_count=2,
    )
    assert event["event_type"] == "retrieval_plan"
    assert event["run_id"] == "run-1"
    assert event["classified_domains"] == ["billing", "account"]
    assert event["query_count"] == 2
    assert len(event["search_queries"]) == 2


def test_log_multi_retrieval_shape():
    event = log_multi_retrieval(
        run_id="run-1",
        attempt=1,
        queries_executed=2,
        total_results=10,
        unique_results=8,
        elapsed_ms=350.0,
    )
    assert event["event_type"] == "multi_retrieval"
    assert event["run_id"] == "run-1"
    assert event["attempt"] == 1
    assert event["queries_executed"] == 2
    assert event["total_results"] == 10
    assert event["unique_results"] == 8
    assert event["elapsed_ms"] == 350.0


def test_log_confidence_assessment_shape():
    event = log_confidence_assessment(
        run_id="run-1",
        attempt=1,
        score=0.75,
        result_count=5,
        avg_similarity=0.75,
        should_retry=False,
        reason="Sufficient confidence",
    )
    assert event["event_type"] == "confidence_assessment"
    assert event["run_id"] == "run-1"
    assert event["attempt"] == 1
    assert event["score"] == 0.75
    assert event["result_count"] == 5
    assert event["avg_similarity"] == 0.75
    assert event["should_retry"] is False
    assert event["reason"] == "Sufficient confidence"


def test_log_retrieval_retry_shape():
    event = log_retrieval_retry(
        run_id="run-1",
        attempt=2,
        previous_score=0.3,
        adjusted_params={"k": 10, "domain_filter": "broadened"},
    )
    assert event["event_type"] == "retrieval_retry"
    assert event["run_id"] == "run-1"
    assert event["attempt"] == 2
    assert event["previous_score"] == 0.3
    assert event["adjusted_params"]["k"] == 10


def test_log_knowledge_gap_shape():
    event = log_knowledge_gap(
        run_id="run-1",
        final_attempt=3,
        final_score=0.2,
        reason="Retrieval confidence below threshold after max attempts",
    )
    assert event["event_type"] == "knowledge_gap"
    assert event["run_id"] == "run-1"
    assert event["final_attempt"] == 3
    assert event["final_score"] == 0.2
    assert "threshold" in event["reason"] or "confidence" in event["reason"]


def test_log_retrieval_plan_returns_dict():
    result = log_retrieval_plan(
        run_id="r", classified_domains=["billing"], search_queries=[], query_count=0
    )
    assert isinstance(result, dict)


def test_log_multi_retrieval_returns_dict():
    result = log_multi_retrieval(
        run_id="r",
        attempt=1,
        queries_executed=1,
        total_results=5,
        unique_results=5,
        elapsed_ms=10.0,
    )
    assert isinstance(result, dict)


def test_log_confidence_assessment_returns_dict():
    result = log_confidence_assessment(
        run_id="r",
        attempt=1,
        score=0.5,
        result_count=3,
        avg_similarity=0.5,
        should_retry=True,
        reason="low",
    )
    assert isinstance(result, dict)


def test_log_retrieval_retry_returns_dict():
    result = log_retrieval_retry(run_id="r", attempt=2, previous_score=0.3, adjusted_params={})
    assert isinstance(result, dict)


def test_log_knowledge_gap_returns_dict():
    result = log_knowledge_gap(run_id="r", final_attempt=3, final_score=0.1, reason="gap")
    assert isinstance(result, dict)


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
