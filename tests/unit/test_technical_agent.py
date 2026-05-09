from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

import src.agents.technical_agent as ta


def _make_technical_state(query_text="How do I reset my API key?"):
    return {
        "query_id": "test-query-456",
        "query_text": query_text,
        "messages": [HumanMessage(content=query_text)],
        "classified_domain": "technical",
        "confidence_rationale": "API key related",
        "routed_to_agent": "technical_agent",
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "test-run-789",
        "log_events": [],
    }


MOCK_TECHNICAL_DOCS = [
    {
        "content": "To rotate an API key: navigate to Settings → Developer → API Keys, click 'Rotate'.",
        "metadata": {
            "domain": "technical",
            "doc_id": "tech-1",
            "title": "API Key Management",
            "source_file": "docs/knowledge_base/technical/api-key-management.md",
        },
        "score": 0.91,
    },
    {
        "content": "If you receive a 401 Unauthorized error, verify the key is correctly copied.",
        "metadata": {
            "domain": "technical",
            "doc_id": "tech-2",
            "title": "Troubleshooting Guide",
            "source_file": "docs/knowledge_base/technical/troubleshooting-guide.md",
        },
        "score": 0.85,
    },
]


@patch("src.agents.technical_agent.retrieve_documents", return_value=MOCK_TECHNICAL_DOCS)
@patch("src.agents.technical_agent.ChatOpenAI")
def test_technical_agent_retrieves_with_technical_domain(mock_anthropic_cls, mock_retrieve):
    mock_llm = MagicMock()
    mock_anthropic_cls.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(
        content="To reset your API key, go to Settings → Developer."
    )

    state = _make_technical_state()
    ta.technical_agent(state)

    mock_retrieve.assert_called_once()
    assert mock_retrieve.call_args[1].get("domain") == "technical"


@patch("src.agents.technical_agent.retrieve_documents", return_value=MOCK_TECHNICAL_DOCS)
@patch("src.agents.technical_agent.ChatOpenAI")
def test_technical_agent_returns_non_empty_citations(mock_anthropic_cls, mock_retrieve):
    mock_llm = MagicMock()
    mock_anthropic_cls.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="Follow these steps to rotate your API key.")

    state = _make_technical_state()
    result = ta.technical_agent(state)

    assert len(result["citations"]) > 0


@patch("src.agents.technical_agent.retrieve_documents", return_value=MOCK_TECHNICAL_DOCS)
@patch("src.agents.technical_agent.ChatOpenAI")
def test_technical_agent_emits_log_events(mock_anthropic_cls, mock_retrieve):
    mock_llm = MagicMock()
    mock_anthropic_cls.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="Response")

    state = _make_technical_state()
    result = ta.technical_agent(state)

    event_types = [e["event_type"] for e in result.get("log_events", [])]
    assert "retrieval" in event_types
    assert "llm_call" in event_types


@patch("src.agents.technical_agent.retrieve_documents", return_value=[])
@patch("src.agents.technical_agent.ChatOpenAI")
def test_technical_agent_handles_no_results(mock_anthropic_cls, mock_retrieve):
    mock_llm = MagicMock()
    mock_anthropic_cls.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="I don't have specific info for this.")

    state = _make_technical_state()
    result = ta.technical_agent(state)

    assert result["response_text"] is not None
    assert len(result["response_text"]) > 0
