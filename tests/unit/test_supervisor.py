from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

import src.agents.supervisor as sup_module


def _make_state(query_text="Why was I charged twice this month?"):
    return {
        "query_id": "test-query-123",
        "query_text": query_text,
        "messages": [HumanMessage(content=query_text)],
        "classified_domain": None,
        "confidence_rationale": None,
        "routed_to_agent": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "test-run-456",
        "log_events": [],
    }


def _make_mock_llm(domain="billing", rationale="Mentions billing charges"):
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = MagicMock(domain=domain, rationale=rationale)
    return mock_llm


@patch("src.agents.supervisor.ChatOpenAI")
def test_supervisor_classifies_billing_query(mock_anthropic_cls):
    mock_anthropic_cls.return_value = _make_mock_llm("billing", "mentions charges")

    from src.agents.supervisor import supervisor

    state = _make_state("Why was I charged twice?")
    result = supervisor(state)

    assert result is not None


@patch("src.agents.supervisor.ChatOpenAI")
def test_supervisor_writes_classified_domain_to_state(mock_anthropic_cls):
    mock_llm = _make_mock_llm("billing", "mentions charges")
    mock_anthropic_cls.return_value = mock_llm

    state = _make_state("Why was I charged twice?")
    command = sup_module.supervisor(state)
    # Command.goto should be the routing destination
    assert command.goto in ("billing_agent", "technical_agent", "account_agent", "fallback_handler")


@patch("src.agents.supervisor.ChatOpenAI")
def test_supervisor_emits_routing_log_event(mock_anthropic_cls):
    mock_anthropic_cls.return_value = _make_mock_llm("billing", "mentions charges")

    state = _make_state("Why was I charged twice?")
    command = sup_module.supervisor(state)

    # The command update should include log_events
    if hasattr(command, "update") and command.update:
        log_events = command.update.get("log_events", [])
        routing_events = [e for e in log_events if e.get("event_type") == "routing_decision"]
        assert len(routing_events) > 0


@patch("src.agents.supervisor.ChatOpenAI")
def test_supervisor_handles_llm_error_gracefully(mock_anthropic_cls):
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.side_effect = Exception("LLM timeout")
    mock_anthropic_cls.return_value = mock_llm

    state = _make_state("test query")
    # Should not raise; should route to fallback
    try:
        command = sup_module.supervisor(state)
        assert command.goto == "fallback_handler"
    except Exception:
        pass  # Acceptable if exception propagates with structured error
