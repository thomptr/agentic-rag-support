from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.message import add_messages

from src.graph.state import SupportGraphState, _accumulate


def test_state_accepts_valid_data():
    state: SupportGraphState = {
        "query_id": "test-id",
        "query_text": "test query",
        "messages": [],
        "classified_domain": None,
        "confidence_rationale": None,
        "current_node": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "run-123",
        "log_events": [],
        # new 002 fields
        "classified_domains": None,
        "search_queries": None,
        "raw_retrieval_results": None,
        "merged_results": None,
        "retrieval_confidence": None,
        "retrieval_attempt": 0,
        "max_retrieval_attempts": 3,
    }
    assert state["query_id"] == "test-id"
    assert state["classified_domain"] is None
    assert state["log_events"] == []


def test_state_classified_domain_values():
    for domain in ("billing", "technical", "account", "unknown"):
        state: SupportGraphState = {
            "query_id": "id",
            "query_text": "q",
            "messages": [],
            "classified_domain": domain,
            "confidence_rationale": "reason",
            "current_node": f"{domain}_agent",
            "retrieved_documents": None,
            "response_text": None,
            "citations": None,
            "run_id": "run-1",
            "log_events": [],
            "classified_domains": None,
            "search_queries": None,
            "raw_retrieval_results": None,
            "merged_results": None,
            "retrieval_confidence": None,
            "retrieval_attempt": 0,
            "max_retrieval_attempts": 3,
        }
        assert state["classified_domain"] == domain


def test_state_classified_domains_multi():
    state: SupportGraphState = {
        "query_id": "id",
        "query_text": "q",
        "messages": [],
        "classified_domain": None,
        "confidence_rationale": None,
        "current_node": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "run-1",
        "log_events": [],
        "classified_domains": ["billing", "account"],
        "search_queries": None,
        "raw_retrieval_results": None,
        "merged_results": None,
        "retrieval_confidence": None,
        "retrieval_attempt": 1,
        "max_retrieval_attempts": 3,
    }
    assert state["classified_domains"] == ["billing", "account"]
    assert state["retrieval_attempt"] == 1
    assert state["max_retrieval_attempts"] == 3


def test_state_search_queries_format():
    queries = [
        {"query": "double charge dispute", "target_domain": "billing", "aspect": "billing concern"},
        {"query": "account locked access", "target_domain": "account", "aspect": "access concern"},
    ]
    state: SupportGraphState = {
        "query_id": "id",
        "query_text": "q",
        "messages": [],
        "classified_domain": None,
        "confidence_rationale": None,
        "current_node": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "run-1",
        "log_events": [],
        "classified_domains": ["billing", "account"],
        "search_queries": queries,
        "raw_retrieval_results": None,
        "merged_results": None,
        "retrieval_confidence": None,
        "retrieval_attempt": 1,
        "max_retrieval_attempts": 3,
    }
    assert len(state["search_queries"]) == 2
    assert state["search_queries"][0]["target_domain"] == "billing"


def test_state_retrieval_confidence_format():
    confidence = {
        "score": 0.85,
        "result_count": 5,
        "avg_similarity": 0.85,
        "should_retry": False,
        "reason": "Sufficient results with high similarity",
    }
    state: SupportGraphState = {
        "query_id": "id",
        "query_text": "q",
        "messages": [],
        "classified_domain": None,
        "confidence_rationale": None,
        "current_node": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "run-1",
        "log_events": [],
        "classified_domains": ["billing"],
        "search_queries": [],
        "raw_retrieval_results": None,
        "merged_results": None,
        "retrieval_confidence": confidence,
        "retrieval_attempt": 1,
        "max_retrieval_attempts": 3,
    }
    assert state["retrieval_confidence"]["should_retry"] is False
    assert state["retrieval_confidence"]["score"] == 0.85


def test_raw_retrieval_results_accumulate_reducer():
    batch1 = [{"content": "doc1", "score": 0.9}]
    batch2 = [{"content": "doc2", "score": 0.8}]
    result = _accumulate(batch1, batch2)
    assert len(result) == 2
    assert result[0]["content"] == "doc1"
    assert result[1]["content"] == "doc2"


def test_accumulate_with_empty():
    result = _accumulate([], [{"content": "doc1"}])
    assert len(result) == 1


def test_add_messages_reducer_accumulates():
    msgs1 = [HumanMessage(content="hello")]
    msgs2 = [AIMessage(content="world")]
    result = add_messages(msgs1, msgs2)
    assert len(result) == 2
    assert result[0].content == "hello"
    assert result[1].content == "world"


def test_log_events_accumulator():
    a = [{"event_type": "llm_call", "run_id": "r1"}]
    b = [{"event_type": "retrieval", "run_id": "r1"}]
    result = a + b
    assert len(result) == 2
    assert result[0]["event_type"] == "llm_call"
    assert result[1]["event_type"] == "retrieval"


def test_log_events_starts_empty():
    state: SupportGraphState = {
        "query_id": "id",
        "query_text": "q",
        "messages": [],
        "classified_domain": None,
        "confidence_rationale": None,
        "current_node": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "run-1",
        "log_events": [],
        "classified_domains": None,
        "search_queries": None,
        "raw_retrieval_results": None,
        "merged_results": None,
        "retrieval_confidence": None,
        "retrieval_attempt": 0,
        "max_retrieval_attempts": 3,
    }
    assert state["log_events"] == []
