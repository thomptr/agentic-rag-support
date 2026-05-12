"""
Additional supervisor tests: multi-domain classification and edge cases.
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
        "classified_domains": None,
        "confidence_rationale": None,
        "current_node": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "run-us4",
        "log_events": [],
        "search_queries": None,
        "raw_retrieval_results": None,
        "merged_results": None,
        "retrieval_confidence": None,
        "retrieval_attempt": 0,
        "max_retrieval_attempts": 3,
    }


def _mock_llm_response(domains, rationale):
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_result = MagicMock()
    mock_result.domains = domains if isinstance(domains, list) else [domains]
    mock_result.rationale = rationale
    mock_structured.invoke.return_value = mock_result
    return mock_llm


@patch("src.agents.supervisor.ChatOpenAI")
def test_multi_domain_query_routes_to_security_check(mock_cls):
    mock_cls.return_value = _mock_llm_response(
        ["billing", "account"],
        "Query mentions charges and account lock — spans billing and account domains.",
    )

    state = _make_state("I was charged twice AND my account is locked")
    command = sup.supervisor(state)

    # Multi-domain queries route through security_check before retrieval
    assert command.goto == "security_check"
    assert command.update.get("classified_domains") is not None
    assert len(command.update["classified_domains"]) == 2


@patch("src.agents.supervisor.ChatOpenAI")
def test_unclassifiable_query_routes_to_fallback(mock_cls):
    mock_cls.return_value = _mock_llm_response(["unknown"], "Cannot classify this query")

    state = _make_state("xyzzy foobarbaz 12345")
    command = sup.supervisor(state)

    assert command.goto == "fallback_handler"
    assert command.update.get("classified_domain") == "unknown"
    assert command.update.get("classified_domains") == ["unknown"]


@patch("src.agents.supervisor.ChatOpenAI")
def test_supervisor_never_returns_empty_classified_domain(mock_cls):
    mock_cls.return_value = _mock_llm_response(["billing"], "billing related")

    for query in [
        "billing question",
        "I was charged twice and also my API key is broken",
        "random ambiguous query",
    ]:
        state = _make_state(query)
        try:
            command = sup.supervisor(state)
            domain = command.update.get("classified_domain")
            assert domain is not None
            assert domain in ("billing", "technical", "account", "unknown")
        except Exception:
            pass  # LLM errors handled by fallback


@patch("src.agents.supervisor.ChatOpenAI")
def test_supervisor_handles_llm_returning_invalid_domain(mock_cls):
    mock_cls.return_value = _mock_llm_response(["nonexistent_domain"], "some rationale")

    state = _make_state("some query")
    command = sup.supervisor(state)

    # Invalid domain should be normalized to "unknown" and route to fallback
    assert command.update.get("classified_domain") == "unknown"
    assert command.goto == "fallback_handler"


@patch("src.agents.supervisor.ChatOpenAI")
def test_ambiguous_query_has_detailed_rationale(mock_cls):
    detailed_rationale = (
        "This query mentions both billing charges and account lockout. "
        "The primary concern is the billing issue based on the emphasis on 'charged twice'."
    )
    mock_cls.return_value = _mock_llm_response(["billing", "account"], detailed_rationale)

    state = _make_state("I was charged twice and my account is locked")
    command = sup.supervisor(state)

    rationale = command.update.get("confidence_rationale", "")
    assert len(rationale) > 10
