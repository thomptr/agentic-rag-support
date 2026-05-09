from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

import src.agents.billing_agent as ba


def _make_billing_state(query_text="Why was I charged twice?"):
    return {
        "query_id": "test-query-123",
        "query_text": query_text,
        "messages": [HumanMessage(content=query_text)],
        "classified_domain": "billing",
        "confidence_rationale": "Mentions billing charges",
        "routed_to_agent": "billing_agent",
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "test-run-456",
        "log_events": [],
    }


MOCK_BILLING_DOCS = [
    {
        "content": "Our pricing plans include Basic ($9.99/mo), Professional ($29.99/mo).",
        "metadata": {
            "domain": "billing",
            "doc_id": "doc-1",
            "title": "Pricing Plans",
            "source_file": "docs/knowledge_base/billing/pricing-plans.md",
        },
        "score": 0.92,
    },
    {
        "content": "Invoices are generated on the first of each month.",
        "metadata": {
            "domain": "billing",
            "doc_id": "doc-2",
            "title": "Invoice Policies",
            "source_file": "docs/knowledge_base/billing/invoice-policies.md",
        },
        "score": 0.87,
    },
]


@patch("src.agents.billing_agent.retrieve_documents", return_value=MOCK_BILLING_DOCS)
@patch("src.agents.billing_agent.ChatOpenAI")
def test_billing_agent_retrieves_docs_with_billing_domain(mock_anthropic_cls, mock_retrieve):
    mock_llm = MagicMock()
    mock_anthropic_cls.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(
        content="Your charge is explained by the pricing plan."
    )

    state = _make_billing_state()
    ba.billing_agent(state)

    mock_retrieve.assert_called_once()
    call_kwargs = mock_retrieve.call_args[1]
    assert call_kwargs.get("domain") == "billing"


@patch("src.agents.billing_agent.retrieve_documents", return_value=MOCK_BILLING_DOCS)
@patch("src.agents.billing_agent.ChatOpenAI")
def test_billing_agent_returns_non_empty_citations(mock_anthropic_cls, mock_retrieve):
    mock_llm = MagicMock()
    mock_anthropic_cls.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(
        content="Based on pricing plans, your charge is correct."
    )

    state = _make_billing_state()
    result = ba.billing_agent(state)

    assert "citations" in result
    assert result["citations"] is not None
    assert len(result["citations"]) > 0


@patch("src.agents.billing_agent.retrieve_documents", return_value=MOCK_BILLING_DOCS)
@patch("src.agents.billing_agent.ChatOpenAI")
def test_billing_agent_emits_retrieval_and_llm_events(mock_anthropic_cls, mock_retrieve):
    mock_llm = MagicMock()
    mock_anthropic_cls.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="Response text")

    state = _make_billing_state()
    result = ba.billing_agent(state)

    log_events = result.get("log_events", [])
    event_types = [e.get("event_type") for e in log_events]
    assert "retrieval" in event_types
    assert "llm_call" in event_types


@patch("src.agents.billing_agent.retrieve_documents", return_value=[])
@patch("src.agents.billing_agent.ChatOpenAI")
def test_billing_agent_handles_no_retrieval_results(mock_anthropic_cls, mock_retrieve):
    mock_llm = MagicMock()
    mock_anthropic_cls.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(
        content="I don't have specific information for your query."
    )

    state = _make_billing_state()
    result = ba.billing_agent(state)

    assert "response_text" in result
    assert result["response_text"] is not None
    assert len(result["response_text"]) > 0


@patch("src.agents.billing_agent.retrieve_documents", return_value=MOCK_BILLING_DOCS)
@patch("src.agents.billing_agent.ChatOpenAI")
def test_billing_agent_returns_response_text(mock_anthropic_cls, mock_retrieve):
    mock_llm = MagicMock()
    mock_anthropic_cls.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="The charge is for your monthly subscription.")

    state = _make_billing_state()
    result = ba.billing_agent(state)

    assert result.get("response_text") == "The charge is for your monthly subscription."
