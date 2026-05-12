from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

import src.agents.supervisor as sup_module


def _make_state(query_text="Why was I charged twice this month?"):
    return {
        "query_id": "test-query-123",
        "query_text": query_text,
        "messages": [HumanMessage(content=query_text)],
        "classified_domain": None,
        "classified_domains": None,
        "confidence_rationale": None,
        "current_node": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "test-run-456",
        "log_events": [],
        "search_queries": None,
        "raw_retrieval_results": None,
        "merged_results": None,
        "retrieval_confidence": None,
        "retrieval_attempt": 0,
        "max_retrieval_attempts": 3,
    }


def _make_mock_llm_single(domain="billing", rationale="Mentions billing charges"):
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_result = MagicMock()
    mock_result.domains = [domain]
    mock_result.rationale = rationale
    mock_structured.invoke.return_value = mock_result
    return mock_llm


def _make_mock_llm_multi(domains, rationale="Multi-domain query"):
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_result = MagicMock()
    mock_result.domains = domains
    mock_result.rationale = rationale
    mock_structured.invoke.return_value = mock_result
    return mock_llm


@patch("src.agents.supervisor.ChatOpenAI")
def test_supervisor_single_domain_returns_one_domain(mock_cls):
    mock_cls.return_value = _make_mock_llm_single("billing", "mentions charges")

    state = _make_state("Why was I charged twice?")
    command = sup_module.supervisor(state)

    assert command is not None
    update = command.update
    assert "classified_domains" in update
    assert len(update["classified_domains"]) == 1
    assert update["classified_domains"][0] == "billing"


@patch("src.agents.supervisor.ChatOpenAI")
def test_supervisor_dual_domain_returns_two_domains(mock_cls):
    mock_cls.return_value = _make_mock_llm_multi(
        ["billing", "account"], "Billing charge and account locked"
    )

    state = _make_state("I was charged twice and now my account is locked")
    command = sup_module.supervisor(state)

    update = command.update
    assert "classified_domains" in update
    assert len(update["classified_domains"]) == 2
    assert "billing" in update["classified_domains"]
    assert "account" in update["classified_domains"]


@patch("src.agents.supervisor.ChatOpenAI")
def test_supervisor_all_domains_returns_three(mock_cls):
    mock_cls.return_value = _make_mock_llm_multi(
        ["billing", "technical", "account"], "Spans all domains"
    )

    state = _make_state("API failing, account locked, and I'm being charged wrong")
    command = sup_module.supervisor(state)

    update = command.update
    assert len(update["classified_domains"]) == 3


@patch("src.agents.supervisor.ChatOpenAI")
def test_supervisor_unknown_routes_to_fallback(mock_cls):
    mock_cls.return_value = _make_mock_llm_multi(["unknown"], "Cannot classify")

    state = _make_state("What is the weather today?")
    command = sup_module.supervisor(state)

    assert command.goto == "fallback_handler"


@patch("src.agents.supervisor.ChatOpenAI")
def test_supervisor_classifiable_routes_to_security_check(mock_cls):
    mock_cls.return_value = _make_mock_llm_single("billing", "mentions charges")

    state = _make_state("Why was I charged twice?")
    command = sup_module.supervisor(state)

    assert command.goto == "security_check"


@patch("src.agents.supervisor.ChatOpenAI")
def test_supervisor_emits_routing_log_event(mock_cls):
    mock_cls.return_value = _make_mock_llm_single("billing", "mentions charges")

    state = _make_state("Why was I charged twice?")
    command = sup_module.supervisor(state)

    if hasattr(command, "update") and command.update:
        log_events = command.update.get("log_events", [])
        routing_events = [e for e in log_events if e.get("event_type") == "routing_decision"]
        assert len(routing_events) > 0


@patch("src.agents.supervisor.ChatOpenAI")
def test_supervisor_handles_llm_error_gracefully(mock_cls):
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.side_effect = Exception("LLM timeout")
    mock_cls.return_value = mock_llm

    state = _make_state("test query")
    command = sup_module.supervisor(state)
    assert command.goto == "fallback_handler"
