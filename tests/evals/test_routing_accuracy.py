"""
Routing accuracy eval suite (T054).
Requires real LLM — mark with @pytest.mark.eval.
Run with: pytest tests/evals/ -m eval -v
Assert >= 90% correct routing (SC-001).
Assert every non-fallback response includes at least one citation (SC-002).
"""

import pytest

pytestmark = pytest.mark.eval

TEST_QUERIES = [
    # Billing queries (3)
    ("Why was I charged twice this month?", "billing"),
    ("Can I get a refund on my annual subscription?", "billing"),
    ("What are the pricing plans available?", "billing"),
    # Technical queries (3)
    ("How do I reset my API key?", "technical"),
    ("I'm getting a 429 rate limit error on my API calls.", "technical"),
    ("How do I set up a webhook integration?", "technical"),
    # Account queries (3)
    ("How do I enable two-factor authentication?", "account"),
    ("I can't log into my account — it keeps saying invalid password.", "account"),
    ("How do I grant admin access to another team member?", "account"),
    # Ambiguous/multi-domain (3)
    ("I was charged twice and now my account is locked", "billing"),  # Primary: billing
    (
        "My API key is invalid and I need to update my account email",
        "technical",
    ),  # Primary: technical
    (
        "I think my account was hacked and there are unauthorized charges",
        "account",
    ),  # Primary: account (security concern)
]

ACCOUNT_TAKEOVER_QUERIES = [
    "Someone logged into my account without my permission",
    "I think my account was compromised",
]


@pytest.mark.parametrize("query_text,expected_domain", TEST_QUERIES)
def test_routing_accuracy_per_query(query_text, expected_domain):
    """Each query should route to the correct domain."""
    from src.graph.workflow import graph

    initial_state = {
        "query_id": "eval-query",
        "query_text": query_text,
        "messages": [],
        "classified_domain": None,
        "confidence_rationale": None,
        "routed_to_agent": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "eval-run",
        "log_events": [],
    }

    result = graph.invoke(initial_state)
    actual_domain = result.get("classified_domain")
    assert actual_domain == expected_domain, (
        f"Query: '{query_text}'\nExpected: {expected_domain}\nActual: {actual_domain}\n"
        f"Rationale: {result.get('confidence_rationale')}"
    )


def test_overall_routing_accuracy():
    """Assert >= 90% routing accuracy across all test queries (SC-001)."""
    from src.graph.workflow import graph

    correct = 0
    total = len(TEST_QUERIES)

    for query_text, expected_domain in TEST_QUERIES:
        initial_state = {
            "query_id": "eval-acc",
            "query_text": query_text,
            "messages": [],
            "classified_domain": None,
            "confidence_rationale": None,
            "routed_to_agent": None,
            "retrieved_documents": None,
            "response_text": None,
            "citations": None,
            "run_id": "eval-run-acc",
            "log_events": [],
        }
        result = graph.invoke(initial_state)
        if result.get("classified_domain") == expected_domain:
            correct += 1

    accuracy = correct / total
    assert accuracy >= 0.9, f"Routing accuracy {accuracy:.1%} below 90% threshold (SC-001)"


def test_worker_responses_include_citations():
    """Assert every non-fallback response has at least one citation (SC-002)."""
    from src.graph.workflow import graph

    for query_text, expected_domain in TEST_QUERIES:
        initial_state = {
            "query_id": "eval-cite",
            "query_text": query_text,
            "messages": [],
            "classified_domain": None,
            "confidence_rationale": None,
            "routed_to_agent": None,
            "retrieved_documents": None,
            "response_text": None,
            "citations": None,
            "run_id": "eval-run-cite",
            "log_events": [],
        }
        result = graph.invoke(initial_state)

        if result.get("routed_to_agent") != "fallback_handler":
            citations = result.get("citations") or []
            assert len(citations) > 0, f"No citations for non-fallback response to: '{query_text}'"


@pytest.mark.parametrize("takeover_query", ACCOUNT_TAKEOVER_QUERIES)
def test_account_takeover_triggers_escalation(takeover_query):
    """Account takeover queries must always trigger escalation (SC-005)."""
    from src.graph.workflow import graph

    initial_state = {
        "query_id": "eval-ato",
        "query_text": takeover_query,
        "messages": [],
        "classified_domain": None,
        "confidence_rationale": None,
        "routed_to_agent": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "eval-run-ato",
        "log_events": [],
    }

    result = graph.invoke(initial_state)
    log_events = result.get("log_events", [])
    escalation_events = [e for e in log_events if e.get("event_type") == "escalation_triggered"]
    assert len(escalation_events) > 0, (
        f"No escalation triggered for takeover query: '{takeover_query}'"
    )
