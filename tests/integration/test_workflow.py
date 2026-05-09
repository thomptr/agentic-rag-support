from unittest.mock import MagicMock, patch

import pytest

from src.graph import workflow as wf_module

pytestmark = pytest.mark.integration


def _billing_state():
    return {
        "query_id": "integ-query-001",
        "query_text": "Why was I charged twice this month?",
        "messages": [],
        "classified_domain": None,
        "confidence_rationale": None,
        "routed_to_agent": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "integ-run-001",
        "log_events": [],
    }


def _technical_state():
    return {
        "query_id": "integ-query-002",
        "query_text": "How do I reset my API key?",
        "messages": [],
        "classified_domain": None,
        "confidence_rationale": None,
        "routed_to_agent": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "integ-run-002",
        "log_events": [],
    }


def _account_state():
    return {
        "query_id": "integ-query-003",
        "query_text": "How do I set up MFA for my account?",
        "messages": [],
        "classified_domain": None,
        "confidence_rationale": None,
        "routed_to_agent": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "integ-run-003",
        "log_events": [],
    }


def _unroutable_state():
    return {
        "query_id": "integ-query-004",
        "query_text": "xyzzy foobarbaz unroutable query 12345",
        "messages": [],
        "classified_domain": None,
        "confidence_rationale": None,
        "routed_to_agent": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "integ-run-004",
        "log_events": [],
    }


@patch("src.agents.supervisor.ChatOpenAI")
def test_billing_query_routes_to_billing_agent(mock_anthropic_cls):
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = MagicMock(domain="billing", rationale="billing charges")
    mock_anthropic_cls.return_value = mock_llm

    result = wf_module.graph.invoke(_billing_state())

    assert result.get("classified_domain") == "billing"
    assert result.get("routed_to_agent") == "billing_agent"
    assert result.get("response_text") is not None


@patch("src.agents.supervisor.ChatOpenAI")
def test_full_workflow_returns_citations(mock_anthropic_cls):
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = MagicMock(domain="billing", rationale="billing")
    mock_anthropic_cls.return_value = mock_llm

    result = wf_module.graph.invoke(_billing_state())

    # Citations may be empty if KB not seeded, but key should exist
    assert "citations" in result


@patch("src.agents.supervisor.ChatOpenAI")
def test_unroutable_query_uses_fallback(mock_anthropic_cls):
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = MagicMock(domain="unknown", rationale="cannot classify")
    mock_anthropic_cls.return_value = mock_llm

    result = wf_module.graph.invoke(_unroutable_state())

    assert result.get("routed_to_agent") == "fallback_handler"
    assert result.get("response_text") is not None
    assert result.get("citations") == []


@patch("src.agents.supervisor.ChatOpenAI")
def test_workflow_includes_routing_decision_log(mock_anthropic_cls):
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = MagicMock(domain="billing", rationale="billing")
    mock_anthropic_cls.return_value = mock_llm

    result = wf_module.graph.invoke(_billing_state())

    log_events = result.get("log_events", [])
    routing_events = [e for e in log_events if e.get("event_type") == "routing_decision"]
    assert len(routing_events) > 0


@patch("src.agents.supervisor.ChatOpenAI")
def test_account_takeover_query_triggers_escalation(mock_anthropic_cls):
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = MagicMock(domain="account", rationale="account security")
    mock_anthropic_cls.return_value = mock_llm

    takeover_state = {
        "query_id": "integ-ato",
        "query_text": "Someone logged into my account without my permission",
        "messages": [],
        "classified_domain": None,
        "confidence_rationale": None,
        "routed_to_agent": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "integ-run-ato",
        "log_events": [],
    }
    result = wf_module.graph.invoke(takeover_state)

    log_events = result.get("log_events", [])
    escalation_events = [e for e in log_events if e.get("event_type") == "escalation_triggered"]
    assert len(escalation_events) > 0


# --- T039: Technical agent routing ---


@patch("src.agents.supervisor.ChatOpenAI")
def test_technical_query_routes_to_technical_agent(mock_anthropic_cls):
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = MagicMock(domain="technical", rationale="API issue")
    mock_anthropic_cls.return_value = mock_llm

    result = wf_module.graph.invoke(_technical_state())

    assert result.get("classified_domain") == "technical"
    assert result.get("routed_to_agent") == "technical_agent"
    assert result.get("response_text") is not None


# --- T046: Account agent routing ---


@patch("src.agents.supervisor.ChatOpenAI")
def test_account_query_routes_to_account_agent(mock_anthropic_cls):
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = MagicMock(domain="account", rationale="MFA setup")
    mock_anthropic_cls.return_value = mock_llm

    result = wf_module.graph.invoke(_account_state())

    assert result.get("classified_domain") == "account"
    assert result.get("routed_to_agent") == "account_agent"
    assert result.get("response_text") is not None


# --- T051: Ambiguous query routing ---


@patch("src.agents.supervisor.ChatOpenAI")
def test_multi_domain_query_gets_routed_not_crashes(mock_anthropic_cls):
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = MagicMock(
        domain="billing",
        rationale="Primary concern is billing charges even though account is also mentioned",
    )
    mock_anthropic_cls.return_value = mock_llm

    ambiguous_state = {
        "query_id": "ambig-001",
        "query_text": "I was charged twice AND my account is locked",
        "messages": [],
        "classified_domain": None,
        "confidence_rationale": None,
        "routed_to_agent": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "ambig-run-001",
        "log_events": [],
    }

    result = wf_module.graph.invoke(ambiguous_state)
    # Should route somewhere valid — not crash
    assert result.get("classified_domain") in ("billing", "technical", "account", "unknown")
    assert result.get("response_text") is not None
    # Routing rationale should exist
    assert result.get("confidence_rationale") is not None


@patch("src.agents.supervisor.ChatOpenAI")
def test_genuinely_unroutable_query_uses_fallback(mock_anthropic_cls):
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = MagicMock(domain="unknown", rationale="unroutable")
    mock_anthropic_cls.return_value = mock_llm

    result = wf_module.graph.invoke(_unroutable_state())

    assert result.get("routed_to_agent") == "fallback_handler"
    assert result.get("citations") == []
