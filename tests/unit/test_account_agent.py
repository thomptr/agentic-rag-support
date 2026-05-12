"""Unit tests for account_agent.

After the domain-agents refactor, account_agent reads documents from
`state["merged_results"]` (populated by the shared multi_retriever pipeline)
rather than calling retrieve_documents itself. The takeover-detection
behavior is preserved.
"""

import re
from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

import src.agents.account_agent as aa

MOCK_ACCOUNT_DOCS = [
    {
        "content": "To set up MFA: download an authenticator app, go to Settings → Security → MFA, scan QR code.",
        "doc_id": "acc-1",
        "title": "MFA Setup",
        "source_file": "docs/knowledge_base/account/mfa-setup.md",
        "domain": "account",
        "score": 0.93,
    },
    {
        "content": "Login troubleshooting: check Caps Lock, verify email address, try password reset.",
        "doc_id": "acc-2",
        "title": "Login Procedures",
        "source_file": "docs/knowledge_base/account/login-procedures.md",
        "domain": "account",
        "score": 0.88,
    },
]


def _make_account_state(query_text="How do I set up MFA?", docs=None):
    return {
        "query_id": "test-query-789",
        "query_text": query_text,
        "messages": [HumanMessage(content=query_text)],
        "classified_domain": "account",
        "confidence_rationale": "MFA related",
        "current_node": "account_agent",
        "retrieved_documents": None,
        "merged_results": docs if docs is not None else MOCK_ACCOUNT_DOCS,
        "response_text": None,
        "citations": None,
        "run_id": "test-run-abc",
        "log_events": [],
    }


# --- Basic RAG behavior ---


@patch("src.agents.account_agent.ChatOpenAI")
def test_account_agent_uses_state_merged_results(mock_llm_cls):
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(
        content="To set up MFA, download an authenticator app."
    )
    result = aa.account_agent(_make_account_state())
    assert result["current_node"] == "account_agent"
    assert len(result["citations"]) == 2


@patch("src.agents.account_agent.ChatOpenAI")
def test_account_agent_returns_citations(mock_llm_cls):
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="MFA setup steps.")
    result = aa.account_agent(_make_account_state())
    assert len(result["citations"]) > 0


@patch("src.agents.account_agent.ChatOpenAI")
def test_account_agent_emits_log_events(mock_llm_cls):
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="Response")
    result = aa.account_agent(_make_account_state())
    event_types = [e["event_type"] for e in result.get("log_events", [])]
    assert "llm_call" in event_types


@patch("src.agents.account_agent.ChatOpenAI")
def test_account_agent_handles_no_results(mock_llm_cls):
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="I don't have info for that.")
    result = aa.account_agent(_make_account_state(docs=[]))
    assert result["response_text"]
    assert result["citations"] == []


# --- Sensitive data safeguards ---


@patch("src.agents.account_agent.ChatOpenAI")
def test_account_agent_response_does_not_expose_passwords(mock_llm_cls):
    """LLM response is the source of truth; agent should not inject sensitive fields itself."""
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(
        content="To reset your password, follow the standard reset procedure."
    )
    result = aa.account_agent(_make_account_state())
    response = result["response_text"]
    # No obvious password/SSN patterns leaked from the agent layer.
    assert not re.search(r"\bP@ssw0rd\d+", response)
    assert not re.search(r"\b\d{3}-\d{2}-\d{4}\b", response)


# --- Takeover detection ---


@patch("src.agents.account_agent.ChatOpenAI")
def test_account_takeover_query_triggers_escalation(mock_llm_cls):
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="Locked down your account.")
    result = aa.account_agent(_make_account_state(query_text="Someone hacked my account!"))
    assert result.get("escalation_flag") is True
    assert result.get("escalation_reason") == "account_takeover"


@patch("src.agents.account_agent.ChatOpenAI")
def test_takeover_response_includes_escalation_guidance(mock_llm_cls):
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="Account secured.")
    result = aa.account_agent(_make_account_state(query_text="Someone accessed my account"))
    assert "SECURITY ALERT" in result["response_text"]


@patch("src.agents.account_agent.ChatOpenAI")
def test_takeover_emits_escalation_event(mock_llm_cls):
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="Account locked.")
    result = aa.account_agent(_make_account_state(query_text="My account was compromised"))
    event_types = [e["event_type"] for e in result.get("log_events", [])]
    assert "escalation_triggered" in event_types


@patch("src.agents.account_agent.ChatOpenAI")
def test_normal_query_does_not_trigger_escalation(mock_llm_cls):
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="MFA setup steps.")
    result = aa.account_agent(_make_account_state())
    assert result.get("escalation_flag") is None
    event_types = [e["event_type"] for e in result.get("log_events", [])]
    assert "escalation_triggered" not in event_types
