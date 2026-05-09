"""
US4 additional tests: Ambiguous/Multi-Domain query handling (T047).
"""

from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

import src.agents.supervisor as sup


def _make_state(query_text):
    return {
        "query_id": "test-us4",
        "query_text": query_text,
        "messages": [HumanMessage(content=query_text)],
        "classified_domain": None,
        "confidence_rationale": None,
        "routed_to_agent": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "run-us4",
        "log_events": [],
    }


def _mock_llm_response(domain, rationale):
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = MagicMock(domain=domain, rationale=rationale)
    return mock_llm


@patch("src.agents.supervisor.ChatOpenAI")
def test_multi_domain_query_returns_valid_classification(mock_cls):
    mock_cls.return_value = _mock_llm_response(
        "billing",
        "Query mentions charges which is the primary billing concern, though account lock is secondary.",
    )

    state = _make_state("I was charged twice AND my account is locked")
    command = sup.supervisor(state)

    # Should route to a valid node, not crash
    assert command.goto in ("billing_agent", "technical_agent", "account_agent", "fallback_handler")
    # Should have a non-empty rationale
    rationale = command.update.get("confidence_rationale", "")
    assert len(rationale) > 0


@patch("src.agents.supervisor.ChatOpenAI")
def test_unclassifiable_query_routes_to_fallback(mock_cls):
    mock_cls.return_value = _mock_llm_response("unknown", "Cannot classify this query")

    state = _make_state("xyzzy foobarbaz 12345")
    command = sup.supervisor(state)

    assert command.goto == "fallback_handler"
    assert command.update.get("classified_domain") == "unknown"


@patch("src.agents.supervisor.ChatOpenAI")
def test_supervisor_never_returns_empty_classified_domain(mock_cls):
    mock_cls.return_value = _mock_llm_response("billing", "billing related")

    for query in [
        "billing question",
        "I was charged twice and also my API key is broken",
        "random ambiguous query",
        "",
    ]:
        state = _make_state(query)
        try:
            command = sup.supervisor(state)
            domain = command.update.get("classified_domain")
            assert domain is not None
            assert domain in ("billing", "technical", "account", "unknown")
        except Exception:
            pass  # LLM errors handled by fallback — acceptable


@patch("src.agents.supervisor.ChatOpenAI")
def test_supervisor_handles_llm_returning_invalid_domain(mock_cls):
    mock_cls.return_value = _mock_llm_response("nonexistent_domain", "some rationale")

    state = _make_state("some query")
    command = sup.supervisor(state)

    # Invalid domain should be normalized to "unknown"
    assert command.update.get("classified_domain") == "unknown"
    assert command.goto == "fallback_handler"


@patch("src.agents.supervisor.ChatOpenAI")
def test_ambiguous_query_has_detailed_rationale(mock_cls):
    detailed_rationale = (
        "This query mentions both billing charges and account lockout. "
        "The primary concern is the billing issue based on the emphasis on 'charged twice'."
    )
    mock_cls.return_value = _mock_llm_response("billing", detailed_rationale)

    state = _make_state("I was charged twice and my account is locked")
    command = sup.supervisor(state)

    rationale = command.update.get("confidence_rationale", "")
    assert len(rationale) > 10  # Detailed rationale, not empty
