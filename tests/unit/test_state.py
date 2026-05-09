from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.message import add_messages

from src.graph.state import SupportGraphState


def test_state_accepts_valid_data():
    state: SupportGraphState = {
        "query_id": "test-id",
        "query_text": "test query",
        "messages": [],
        "classified_domain": None,
        "confidence_rationale": None,
        "routed_to_agent": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "run-123",
        "log_events": [],
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
            "routed_to_agent": f"{domain}_agent",
            "retrieved_documents": None,
            "response_text": None,
            "citations": None,
            "run_id": "run-1",
            "log_events": [],
        }
        assert state["classified_domain"] == domain


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
        "routed_to_agent": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "run-1",
        "log_events": [],
    }
    assert state["log_events"] == []
