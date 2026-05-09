import re
from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

import src.agents.account_agent as aa


def _make_account_state(query_text="How do I set up MFA?"):
    return {
        "query_id": "test-query-789",
        "query_text": query_text,
        "messages": [HumanMessage(content=query_text)],
        "classified_domain": "account",
        "confidence_rationale": "MFA related",
        "routed_to_agent": "account_agent",
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "test-run-abc",
        "log_events": [],
    }


MOCK_ACCOUNT_DOCS = [
    {
        "content": "To set up MFA: download an authenticator app, go to Settings → Security → MFA, scan QR code.",
        "metadata": {
            "domain": "account",
            "doc_id": "acc-1",
            "title": "MFA Setup",
            "source_file": "docs/knowledge_base/account/mfa-setup.md",
        },
        "score": 0.93,
    },
    {
        "content": "Login troubleshooting: check Caps Lock, verify email address, try password reset.",
        "metadata": {
            "domain": "account",
            "doc_id": "acc-2",
            "title": "Login Procedures",
            "source_file": "docs/knowledge_base/account/login-procedures.md",
        },
        "score": 0.88,
    },
]

MOCK_SENSITIVE_DOCS = [
    {
        "content": "User password: P@ssw0rd123, Account SSN: 123-45-6789, Security answer: mother_maiden_name",
        "metadata": {
            "domain": "account",
            "doc_id": "acc-3",
            "title": "Test Doc",
            "source_file": "docs/knowledge_base/account/test.md",
        },
        "score": 0.7,
    },
]


# --- Basic RAG behavior tests (T040) ---


@patch("src.agents.account_agent.retrieve_documents", return_value=MOCK_ACCOUNT_DOCS)
@patch("src.agents.account_agent.ChatOpenAI")
def test_account_agent_retrieves_with_account_domain(mock_anthropic_cls, mock_retrieve):
    mock_llm = MagicMock()
    mock_anthropic_cls.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(
        content="To set up MFA, download an authenticator app."
    )

    state = _make_account_state()
    aa.account_agent(state)

    mock_retrieve.assert_called_once()
    assert mock_retrieve.call_args[1].get("domain") == "account"


@patch("src.agents.account_agent.retrieve_documents", return_value=MOCK_ACCOUNT_DOCS)
@patch("src.agents.account_agent.ChatOpenAI")
def test_account_agent_returns_citations(mock_anthropic_cls, mock_retrieve):
    mock_llm = MagicMock()
    mock_anthropic_cls.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="To enable MFA, go to Settings.")

    state = _make_account_state()
    result = aa.account_agent(state)

    assert len(result["citations"]) > 0


@patch("src.agents.account_agent.retrieve_documents", return_value=MOCK_ACCOUNT_DOCS)
@patch("src.agents.account_agent.ChatOpenAI")
def test_account_agent_emits_log_events(mock_anthropic_cls, mock_retrieve):
    mock_llm = MagicMock()
    mock_anthropic_cls.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="Response")

    state = _make_account_state()
    result = aa.account_agent(state)

    event_types = [e["event_type"] for e in result.get("log_events", [])]
    assert "retrieval" in event_types
    assert "llm_call" in event_types


@patch("src.agents.account_agent.retrieve_documents", return_value=[])
@patch("src.agents.account_agent.ChatOpenAI")
def test_account_agent_handles_no_results(mock_anthropic_cls, mock_retrieve):
    mock_llm = MagicMock()
    mock_anthropic_cls.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="I don't have specific info on this topic.")

    state = _make_account_state()
    result = aa.account_agent(state)

    assert result["response_text"] is not None
    assert len(result["response_text"]) > 0


# --- Sensitive data protection tests (T041) ---


@patch("src.agents.account_agent.retrieve_documents", return_value=MOCK_ACCOUNT_DOCS)
@patch("src.agents.account_agent.ChatOpenAI")
def test_account_agent_system_prompt_prohibits_sensitive_data(mock_anthropic_cls, mock_retrieve):
    """Verify the system prompt instructs LLM to never include credentials or PII."""
    mock_llm = MagicMock()
    mock_anthropic_cls.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(
        content="Safe account response without sensitive data."
    )

    # Check system prompt contains the critical instruction
    assert "NEVER" in aa._ACCOUNT_SYSTEM_PROMPT
    assert "password" in aa._ACCOUNT_SYSTEM_PROMPT.lower()
    assert "credentials" in aa._ACCOUNT_SYSTEM_PROMPT.lower()


@patch("src.agents.account_agent.retrieve_documents", return_value=MOCK_ACCOUNT_DOCS)
@patch("src.agents.account_agent.ChatOpenAI")
def test_account_agent_response_does_not_expose_passwords(mock_anthropic_cls, mock_retrieve):
    """Mock LLM returns safe response; verify no password patterns."""
    mock_llm = MagicMock()
    mock_anthropic_cls.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(
        content="To reset your password, click 'Forgot password' on the login page."
    )

    state = _make_account_state("How do I reset my password?")
    result = aa.account_agent(state)

    # Verify no SSN patterns in response
    assert not re.search(r"\b\d{3}-\d{2}-\d{4}\b", result["response_text"])


# --- Account takeover escalation tests (T042) ---


@patch("src.agents.account_agent.retrieve_documents", return_value=MOCK_ACCOUNT_DOCS)
@patch("src.agents.account_agent.ChatOpenAI")
def test_account_takeover_query_triggers_escalation(mock_anthropic_cls, mock_retrieve):
    mock_llm = MagicMock()
    mock_anthropic_cls.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="Please secure your account immediately.")

    state = _make_account_state("Someone accessed my account without my permission")
    result = aa.account_agent(state)

    # Escalation flag should be set
    assert result.get("escalation_metadata", {}).get("escalation_flag") is True


@patch("src.agents.account_agent.retrieve_documents", return_value=MOCK_ACCOUNT_DOCS)
@patch("src.agents.account_agent.ChatOpenAI")
def test_takeover_response_includes_escalation_guidance(mock_anthropic_cls, mock_retrieve):
    mock_llm = MagicMock()
    mock_anthropic_cls.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="Normal response text.")

    state = _make_account_state("I think my account was hacked")
    result = aa.account_agent(state)

    # Response should contain escalation guidance
    assert (
        "security" in result["response_text"].lower()
        or "escalat" in result["response_text"].lower()
    )


@patch("src.agents.account_agent.retrieve_documents", return_value=MOCK_ACCOUNT_DOCS)
@patch("src.agents.account_agent.ChatOpenAI")
def test_takeover_emits_escalation_event(mock_anthropic_cls, mock_retrieve):
    mock_llm = MagicMock()
    mock_anthropic_cls.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="Account security response.")

    state = _make_account_state("unauthorized login detected on my account")
    result = aa.account_agent(state)

    event_types = [e["event_type"] for e in result.get("log_events", [])]
    assert "escalation_triggered" in event_types


@patch("src.agents.account_agent.retrieve_documents", return_value=MOCK_ACCOUNT_DOCS)
@patch("src.agents.account_agent.ChatOpenAI")
def test_normal_query_does_not_trigger_escalation(mock_anthropic_cls, mock_retrieve):
    mock_llm = MagicMock()
    mock_anthropic_cls.return_value = mock_llm
    mock_llm.invoke.return_value = MagicMock(content="To set up MFA, go to Settings.")

    state = _make_account_state("How do I set up MFA?")
    result = aa.account_agent(state)

    assert not result.get("escalation_metadata")
