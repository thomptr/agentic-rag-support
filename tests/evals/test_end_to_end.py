"""
End-to-end validation tests for billing and account agent responsibilities (T052, T053).
These tests verify all design responsibilities from design/Billing Agent.md and design/Account Agent.md.
Mark with @pytest.mark.eval — requires real LLM and seeded knowledge base.
"""

import pytest

pytestmark = pytest.mark.eval


def _invoke_graph(query_text: str) -> dict:
    from src.graph.workflow import graph

    state = {
        "query_id": "e2e-query",
        "query_text": query_text,
        "messages": [],
        "classified_domain": None,
        "confidence_rationale": None,
        "current_node": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "e2e-run",
        "log_events": [],
    }
    return graph.invoke(state)


# --- T052: Billing Agent Responsibility Validation ---


def test_billing_agent_explains_charges():
    result = _invoke_graph("What are your pricing tiers?")
    assert result.get("classified_domain") == "billing"
    assert result.get("response_text")
    citations = result.get("citations", [])
    assert len(citations) > 0
    source_files = [c.get("source_file", "") for c in citations]
    assert any("pricing-plans" in sf for sf in source_files), "Should cite pricing-plans.md"


def test_billing_agent_retrieves_invoice_policies():
    result = _invoke_graph("When is my next invoice generated?")
    assert result.get("classified_domain") == "billing"
    citations = result.get("citations", [])
    assert len(citations) > 0


def test_billing_agent_retrieves_cancellation_terms():
    result = _invoke_graph("What is your cancellation policy?")
    assert result.get("classified_domain") == "billing"
    citations = result.get("citations", [])
    assert len(citations) > 0
    source_files = [c.get("source_file", "") for c in citations]
    assert any("cancellation" in sf for sf in source_files), "Should cite cancellation-terms.md"


def test_billing_agent_determines_refund_eligibility():
    result = _invoke_graph("Am I eligible for a refund on my annual subscription?")
    assert result.get("classified_domain") == "billing"
    response = result.get("response_text", "").lower()
    assert any(word in response for word in ("refund", "eligible", "30-day", "window"))
    citations = result.get("citations", [])
    assert len(citations) > 0


def test_billing_agent_escalates_payment_disputes():
    result = _invoke_graph("I want to dispute a charge on my account")
    assert result.get("classified_domain") == "billing"
    response = result.get("response_text", "").lower()
    assert any(
        word in response
        for word in ("dispute", "chargeback", "human", "billing support", "contact")
    )


# --- T053: Account Agent Responsibility Validation ---


def test_account_agent_handles_login():
    result = _invoke_graph("How do I reset my password?")
    assert result.get("classified_domain") == "account"
    citations = result.get("citations", [])
    assert len(citations) > 0


def test_account_agent_handles_mfa():
    result = _invoke_graph("How do I set up two-factor authentication?")
    assert result.get("classified_domain") == "account"
    citations = result.get("citations", [])
    assert len(citations) > 0
    source_files = [c.get("source_file", "") for c in citations]
    assert any("mfa" in sf for sf in source_files), "Should cite mfa-setup.md"


def test_account_agent_handles_permissions():
    result = _invoke_graph("How do I grant admin access to a team member?")
    assert result.get("classified_domain") == "account"
    citations = result.get("citations", [])
    assert len(citations) > 0


def test_account_agent_handles_security_questions():
    result = _invoke_graph("How do I change my security questions?")
    assert result.get("classified_domain") == "account"
    citations = result.get("citations", [])
    assert len(citations) > 0


def test_account_agent_triggers_escalation_for_takeover():
    result = _invoke_graph("I think someone hacked my account")
    assert result.get("classified_domain") == "account"
    log_events = result.get("log_events", [])
    escalation_events = [e for e in log_events if e.get("event_type") == "escalation_triggered"]
    assert len(escalation_events) > 0, "Account takeover must trigger escalation"


def test_account_agent_no_sensitive_data_in_responses():
    import re

    queries = [
        "How do I reset my password?",
        "How do I set up MFA?",
        "What are my account permissions?",
    ]
    ssn_pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    password_pattern = re.compile(r"\bpassword\s*[:=]\s*\S+", re.IGNORECASE)

    for query in queries:
        result = _invoke_graph(query)
        response = result.get("response_text", "")
        assert not ssn_pattern.search(response), f"SSN pattern found in response for: {query}"
        assert not password_pattern.search(response), (
            f"Password value found in response for: {query}"
        )
