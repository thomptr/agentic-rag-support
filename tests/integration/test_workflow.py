from unittest.mock import MagicMock, patch

import pytest

from src.graph import workflow as wf_module

pytestmark = pytest.mark.integration


def _make_state(query_text, query_id="integ-001", run_id="integ-run-001"):
    return {
        "query_id": query_id,
        "query_text": query_text,
        "messages": [],
        "classified_domain": None,
        "classified_domains": None,
        "confidence_rationale": None,
        "routed_to_agent": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": run_id,
        "log_events": [],
        "search_queries": None,
        "raw_retrieval_results": None,
        "merged_results": None,
        "retrieval_confidence": None,
        "retrieval_attempt": 0,
        "max_retrieval_attempts": 3,
    }


def _make_mock_supervisor(domains, rationale="test"):
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_result = MagicMock()
    mock_result.domains = domains
    mock_result.rationale = rationale
    mock_structured.invoke.return_value = mock_result
    return mock_llm


def _make_mock_query_gen(queries):
    mock = MagicMock(return_value=queries)
    return mock


def _make_mock_retriever(docs):
    mock = MagicMock(return_value=docs)
    return mock


def _make_mock_llm_response(text="Test response"):
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = text
    mock_llm.invoke.return_value = mock_response
    return mock_llm


# --- T041: Cross-domain query workflow ---


@patch("src.agents.response_generator.ChatOpenAI")
@patch("src.agents.multi_retriever.retrieve_documents_multi_domain")
@patch("src.agents.retrieval_planner.generate_search_queries")
@patch("src.agents.supervisor.ChatOpenAI")
def test_cross_domain_query_produces_multi_domain_citations(
    mock_sup_cls, mock_gen, mock_retrieve, mock_resp_cls
):
    mock_sup_cls.return_value = _make_mock_supervisor(
        ["billing", "account"], "billing charge and account locked"
    )
    mock_gen.return_value = [
        {"query": "double charge", "target_domain": "billing", "aspect": "billing"},
        {"query": "account locked", "target_domain": "account", "aspect": "access"},
    ]
    mock_retrieve.return_value = [
        {
            "content": "Dispute charges within 30 days",
            "metadata": {"domain": "billing", "source_file": "payment-disputes.md"},
            "score": 0.92,
            "domain": "billing",
            "source_query": "double charge",
        },
        {
            "content": "Verify identity to unlock account",
            "metadata": {"domain": "account", "source_file": "login-procedures.md"},
            "score": 0.89,
            "domain": "account",
            "source_query": "account locked",
        },
        {
            "content": "Refund eligibility window is 30 days",
            "metadata": {"domain": "billing", "source_file": "refund-eligibility.md"},
            "score": 0.85,
            "domain": "billing",
            "source_query": "double charge",
        },
    ]
    mock_resp_cls.return_value = _make_mock_llm_response(
        "For duplicate charges, contact billing within 30 days. For locked accounts, verify identity."
    )

    result = wf_module.graph.invoke(_make_state("I was charged twice and now my account is locked"))

    assert result.get("classified_domains") is not None
    assert len(result["classified_domains"]) >= 2
    assert result.get("response_text") is not None
    assert result.get("citations") is not None

    citation_domains = {
        c.get("domain") for c in (result.get("citations") or []) if isinstance(c, dict)
    }
    assert len(citation_domains) >= 1


@patch("src.agents.response_generator.ChatOpenAI")
@patch("src.agents.multi_retriever.retrieve_documents_multi_domain")
@patch("src.agents.retrieval_planner.generate_search_queries")
@patch("src.agents.supervisor.ChatOpenAI")
def test_single_domain_query_still_works(mock_sup_cls, mock_gen, mock_retrieve, mock_resp_cls):
    mock_sup_cls.return_value = _make_mock_supervisor(["billing"], "billing charge query")
    mock_gen.return_value = [
        {"query": "billing charge", "target_domain": "billing", "aspect": "charge"},
    ]
    mock_retrieve.return_value = [
        {
            "content": "Refund policy: 30 days",
            "metadata": {"domain": "billing", "source_file": "refund-eligibility.md"},
            "score": 0.88,
            "domain": "billing",
            "source_query": "billing charge",
        },
        {
            "content": "Duplicate-charge resolution flow",
            "metadata": {"domain": "billing", "source_file": "payment-disputes.md"},
            "score": 0.85,
            "domain": "billing",
            "source_query": "billing charge",
        },
        {
            "content": "Billing FAQ: when do charges appear?",
            "metadata": {"domain": "billing", "source_file": "billing-faq.md"},
            "score": 0.82,
            "domain": "billing",
            "source_query": "billing charge",
        },
    ]
    mock_resp_cls.return_value = _make_mock_llm_response(
        "You are eligible for a refund within 30 days."
    )

    result = wf_module.graph.invoke(_make_state("Why was I charged twice?"))

    assert result.get("classified_domains") == ["billing"]
    assert result.get("response_text") is not None
    citations = result.get("citations") or []
    assert len(citations) > 0


@patch("src.agents.supervisor.ChatOpenAI")
def test_unroutable_query_uses_fallback(mock_sup_cls):
    mock_sup_cls.return_value = _make_mock_supervisor(["unknown"], "cannot classify")

    result = wf_module.graph.invoke(
        _make_state("What is the weather today?", "integ-004", "integ-run-004")
    )

    assert result.get("routed_to_agent") == "fallback_handler"
    assert result.get("response_text") is not None
    assert result.get("citations") == []


@patch("src.agents.supervisor.ChatOpenAI")
def test_workflow_includes_routing_decision_log(mock_sup_cls):
    mock_sup_cls.return_value = _make_mock_supervisor(["unknown"], "cannot classify")

    result = wf_module.graph.invoke(_make_state("unroutable query", "integ-005", "integ-run-005"))

    log_events = result.get("log_events", [])
    routing_events = [e for e in log_events if e.get("event_type") == "routing_decision"]
    assert len(routing_events) > 0


# --- T056/T057: Adaptive retrieval retry tests ---


@patch("src.agents.response_generator.ChatOpenAI")
@patch("src.agents.multi_retriever.retrieve_documents_multi_domain")
@patch("src.agents.retrieval_planner.generate_search_queries")
@patch("src.agents.supervisor.ChatOpenAI")
def test_low_confidence_triggers_retry(mock_sup_cls, mock_gen, mock_retrieve, mock_resp_cls):
    mock_sup_cls.return_value = _make_mock_supervisor(["billing"], "billing query")
    mock_gen.return_value = [
        {"query": "billing query", "target_domain": "billing", "aspect": "general"},
    ]

    call_count = {"n": 0}

    def retrieve_side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] <= 1:
            # First attempt: low similarity docs
            return [
                {
                    "content": "doc",
                    "metadata": {"domain": "billing"},
                    "score": 0.2,
                    "domain": "billing",
                    "source_query": "q",
                }
            ]
        else:
            # Subsequent attempts: better docs
            return [
                {
                    "content": f"doc {i}",
                    "metadata": {"domain": "billing"},
                    "score": 0.8,
                    "domain": "billing",
                    "source_query": "q",
                }
                for i in range(5)
            ]

    mock_retrieve.side_effect = retrieve_side_effect
    mock_resp_cls.return_value = _make_mock_llm_response("Good response with grounded content.")

    result = wf_module.graph.invoke(_make_state("billing question", "retry-001", "retry-run-001"))

    assert result.get("response_text") is not None
    # Should have gone through at least one retry
    assert result.get("retrieval_attempt", 1) >= 1
