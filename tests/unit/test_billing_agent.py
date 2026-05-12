"""Unit tests for billing_agent.

After the domain-agents refactor, billing_agent reads documents from
`state["merged_results"]` (populated by the shared multi_retriever pipeline)
rather than calling retrieve_documents itself. Tests mock ChatOpenAI; the
retriever is no longer a per-agent dependency.
"""

from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

import src.agents.billing_agent as ba

MOCK_BILLING_DOCS = [
    {
        "content": "Our pricing plans include Basic ($9.99/mo), Professional ($29.99/mo).",
        "doc_id": "doc-1",
        "title": "Pricing Plans",
        "source_file": "docs/knowledge_base/billing/pricing-plans.md",
        "domain": "billing",
        "score": 0.92,
    },
    {
        "content": "Invoices are generated on the first of each month.",
        "doc_id": "doc-2",
        "title": "Invoice Policies",
        "source_file": "docs/knowledge_base/billing/invoice-policies.md",
        "domain": "billing",
        "score": 0.87,
    },
]


def _make_billing_state(query_text="Why was I charged twice?", docs=None):
    return {
        "query_id": "test-query-123",
        "query_text": query_text,
        "messages": [HumanMessage(content=query_text)],
        "classified_domain": "billing",
        "confidence_rationale": "Mentions billing charges",
        "current_node": "billing_agent",
        "retrieved_documents": None,
        "merged_results": docs if docs is not None else MOCK_BILLING_DOCS,
        "response_text": None,
        "citations": None,
        "run_id": "test-run-456",
        "log_events": [],
    }


@patch("src.agents.billing_agent.ChatOpenAI")
def test_billing_agent_uses_state_merged_results(mock_llm_cls):
    """The agent reads docs from state, not from a per-agent retrieval call."""
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="Your charge is explained.")

    state = _make_billing_state()
    result = ba.billing_agent(state)
    assert result["current_node"] == "billing_agent"
    assert len(result["citations"]) == 2  # both MOCK_BILLING_DOCS surfaced as citations


@patch("src.agents.billing_agent.ChatOpenAI")
def test_billing_agent_returns_non_empty_citations(mock_llm_cls):
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="Based on pricing plans, OK.")

    state = _make_billing_state()
    result = ba.billing_agent(state)

    assert result.get("citations")
    assert len(result["citations"]) > 0


@patch("src.agents.billing_agent.ChatOpenAI")
def test_billing_agent_emits_llm_event(mock_llm_cls):
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="Response text")

    state = _make_billing_state()
    result = ba.billing_agent(state)

    log_events = result.get("log_events", [])
    event_types = [e.get("event_type") for e in log_events]
    assert "llm_call" in event_types


@patch("src.agents.billing_agent.ChatOpenAI")
def test_billing_agent_handles_no_merged_results(mock_llm_cls):
    """When the retrieval pipeline returned no docs, agent still responds."""
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="I don't have info for that.")

    state = _make_billing_state(docs=[])
    result = ba.billing_agent(state)

    assert result.get("response_text")
    assert result.get("citations") == []


@patch("src.agents.billing_agent.ChatOpenAI")
def test_billing_agent_returns_response_text(mock_llm_cls):
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="The charge is for your monthly subscription.")

    state = _make_billing_state()
    result = ba.billing_agent(state)

    assert result.get("response_text") == "The charge is for your monthly subscription."


@patch("src.agents.billing_agent.ChatOpenAI")
def test_billing_agent_sets_action_needed_for_refund_keyword(mock_llm_cls):
    """Refund-intent queries should trigger action_planner downstream."""
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="Refund eligibility info.")

    state = _make_billing_state(query_text="I want a refund for last month's charge.")
    result = ba.billing_agent(state)
    assert result.get("action_needed") is True


@patch("src.agents.billing_agent.ChatOpenAI")
def test_billing_agent_surfaces_bound_tool_calls(mock_llm_cls):
    """When the LLM emits a structured tool call via bind_tools, the agent
    surfaces it in state['tool_calls'] in the executor's expected shape and
    sets action_needed=True regardless of keyword heuristic."""
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(
        content="",
        tool_calls=[
            {
                "name": "issue_refund",
                "args": {"order_id": "ORD-12345", "amount": 49.99, "reason": "defective"},
                "id": "call_1",
                "type": "tool_call",
            }
        ],
    )

    state = _make_billing_state(query_text="Please take care of this for me.")
    result = ba.billing_agent(state)

    assert result.get("action_needed") is True
    tcs = result.get("tool_calls") or []
    assert len(tcs) == 1
    assert tcs[0]["tool_name"] == "issue_refund"
    assert tcs[0]["parameters"]["order_id"] == "ORD-12345"
    assert tcs[0]["risk_level"] == "high"
    assert tcs[0]["reason"] == "llm-selected"
