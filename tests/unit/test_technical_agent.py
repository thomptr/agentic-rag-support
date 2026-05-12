"""Unit tests for technical_agent.

After the domain-agents refactor, technical_agent reads documents from
`state["merged_results"]` (populated by the shared multi_retriever pipeline)
rather than calling retrieve_documents itself.
"""

from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

import src.agents.technical_agent as ta

MOCK_TECHNICAL_DOCS = [
    {
        "content": "To rotate an API key: navigate to Settings → Developer → API Keys, click 'Rotate'.",
        "doc_id": "tech-1",
        "title": "API Key Management",
        "source_file": "docs/knowledge_base/technical/api-key-management.md",
        "domain": "technical",
        "score": 0.91,
    },
    {
        "content": "If you receive a 401 Unauthorized error, verify the key is correctly copied.",
        "doc_id": "tech-2",
        "title": "Troubleshooting Guide",
        "source_file": "docs/knowledge_base/technical/troubleshooting-guide.md",
        "domain": "technical",
        "score": 0.85,
    },
]


def _make_technical_state(query_text="How do I reset my API key?", docs=None):
    return {
        "query_id": "test-query-456",
        "query_text": query_text,
        "messages": [HumanMessage(content=query_text)],
        "classified_domain": "technical",
        "confidence_rationale": "API key related",
        "current_node": "technical_agent",
        "retrieved_documents": None,
        "merged_results": docs if docs is not None else MOCK_TECHNICAL_DOCS,
        "response_text": None,
        "citations": None,
        "run_id": "test-run-789",
        "log_events": [],
    }


@patch("src.agents.technical_agent.ChatOpenAI")
def test_technical_agent_uses_state_merged_results(mock_llm_cls):
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="To reset your API key, go to Settings.")
    result = ta.technical_agent(_make_technical_state())
    assert result["current_node"] == "technical_agent"
    assert len(result["citations"]) == 2


@patch("src.agents.technical_agent.ChatOpenAI")
def test_technical_agent_returns_non_empty_citations(mock_llm_cls):
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="Follow these steps.")
    result = ta.technical_agent(_make_technical_state())
    assert len(result["citations"]) > 0


@patch("src.agents.technical_agent.ChatOpenAI")
def test_technical_agent_emits_llm_event(mock_llm_cls):
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="Response")
    result = ta.technical_agent(_make_technical_state())
    event_types = [e["event_type"] for e in result.get("log_events", [])]
    assert "llm_call" in event_types


@patch("src.agents.technical_agent.ChatOpenAI")
def test_technical_agent_handles_no_results(mock_llm_cls):
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="I don't have specific info for this.")
    result = ta.technical_agent(_make_technical_state(docs=[]))
    assert result["response_text"]
    assert result["citations"] == []


@patch("src.agents.technical_agent.ChatOpenAI")
def test_technical_agent_sets_action_needed_for_ticket_keyword(mock_llm_cls):
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="Please open a ticket.")
    result = ta.technical_agent(
        _make_technical_state(query_text="Please open a support ticket for this bug.")
    )
    assert result.get("action_needed") is True
