"""
Routing accuracy eval suite.
Requires real LLM — mark with @pytest.mark.eval.
Run with: pytest tests/evals/ -m eval -v

Updated for multi-domain classification (002):
- Queries that span multiple domains check that all expected_domains are in classified_domains
- Single-domain queries check primary domain is included
"""

import pytest

pytestmark = pytest.mark.eval

# (query_text, expected_primary_domain, expected_domains_list)
TEST_QUERIES = [
    # Billing queries
    ("Why was I charged twice this month?", "billing", ["billing"]),
    ("Can I get a refund on my annual subscription?", "billing", ["billing"]),
    ("What are the pricing plans available?", "billing", ["billing"]),
    # Technical queries
    ("How do I reset my API key?", "technical", ["technical"]),
    ("I'm getting a 429 rate limit error on my API calls.", "technical", ["technical"]),
    ("How do I set up a webhook integration?", "technical", ["technical"]),
    # Account queries
    ("How do I enable two-factor authentication?", "account", ["account"]),
    ("I can't log into my account — it keeps saying invalid password.", "account", ["account"]),
    ("How do I grant admin access to another team member?", "account", ["account"]),
    # Multi-domain queries (should classify to 2+ domains)
    (
        "I was charged twice and now my account is locked",
        "billing",
        ["billing", "account"],
    ),
    (
        "My API is failing with 429 errors and I need to upgrade my plan",
        "technical",
        ["technical", "billing"],
    ),
]

FALLBACK_QUERIES = [
    "What is the weather today?",
    "Tell me a joke",
    "xyzzy foobarbaz unroutable query 12345",
]


def _make_initial_state(query_text: str) -> dict:
    return {
        "query_id": "eval-query",
        "query_text": query_text,
        "messages": [],
        "classified_domain": None,
        "classified_domains": None,
        "confidence_rationale": None,
        "current_node": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "eval-run",
        "log_events": [],
        "search_queries": None,
        "raw_retrieval_results": None,
        "merged_results": None,
        "retrieval_confidence": None,
        "retrieval_attempt": 0,
        "max_retrieval_attempts": 3,
    }


@pytest.mark.parametrize("query_text,expected_primary,expected_domains", TEST_QUERIES)
def test_routing_accuracy_per_query(query_text, expected_primary, expected_domains):
    """Each query should classify into the expected domain(s)."""
    from src.graph.workflow import graph

    result = graph.invoke(_make_initial_state(query_text))
    classified_domains = result.get("classified_domains") or []

    # Primary domain must be in classified_domains
    assert expected_primary in classified_domains, (
        f"Query: '{query_text}'\n"
        f"Expected primary domain '{expected_primary}' in classified_domains: {classified_domains}\n"
        f"Rationale: {result.get('confidence_rationale')}"
    )


@pytest.mark.parametrize("query_text,expected_primary,expected_domains", TEST_QUERIES)
def test_multi_domain_routing_captures_all_expected_domains(
    query_text, expected_primary, expected_domains
):
    """Multi-domain queries should classify into all expected domains."""
    if len(expected_domains) <= 1:
        pytest.skip("Single-domain query — covered by test_routing_accuracy_per_query")

    from src.graph.workflow import graph

    result = graph.invoke(_make_initial_state(query_text))
    classified_domains = result.get("classified_domains") or []

    for domain in expected_domains:
        assert domain in classified_domains, (
            f"Query: '{query_text}'\n"
            f"Expected domain '{domain}' in classified_domains: {classified_domains}\n"
            f"Rationale: {result.get('confidence_rationale')}"
        )


def test_overall_routing_accuracy():
    """Assert >= 90% routing accuracy across all test queries (SC-001)."""
    from src.graph.workflow import graph

    correct = 0
    total = len(TEST_QUERIES)

    for query_text, expected_primary, _ in TEST_QUERIES:
        result = graph.invoke(_make_initial_state(query_text))
        classified_domains = result.get("classified_domains") or []
        if expected_primary in classified_domains:
            correct += 1

    accuracy = correct / total
    assert accuracy >= 0.9, f"Routing accuracy {accuracy:.1%} below 90% threshold (SC-001)"


def test_classifiable_queries_route_to_retrieval_pipeline():
    """Non-fallback queries should route through the retrieval pipeline."""
    from src.graph.workflow import graph

    for query_text, expected_primary, _ in TEST_QUERIES:
        result = graph.invoke(_make_initial_state(query_text))
        routed_to = result.get("current_node", "")
        assert routed_to != "fallback_handler", (
            f"Expected '{query_text}' to route through retrieval pipeline, "
            f"but it went to fallback_handler"
        )


def test_response_generator_produces_citations():
    """All response_generator responses must have at least one citation (SC-002)."""
    from src.graph.workflow import graph

    for query_text, _, _ in TEST_QUERIES:
        result = graph.invoke(_make_initial_state(query_text))

        if result.get("current_node") == "response_generator":
            citations = result.get("citations") or []
            assert len(citations) > 0, (
                f"No citations for response_generator response to: '{query_text}'"
            )


@pytest.mark.parametrize("query_text", FALLBACK_QUERIES)
def test_unroutable_queries_use_fallback(query_text):
    """Genuinely unroutable queries should use the fallback handler."""
    from src.graph.workflow import graph

    result = graph.invoke(_make_initial_state(query_text))
    assert result.get("current_node") == "fallback_handler", (
        f"Expected '{query_text}' to use fallback, got: {result.get('current_node')}"
    )
