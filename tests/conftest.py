import os

import pytest

# Strip LANGFUSE_* credentials before the test session loads any modules so
# observability code paths don't accidentally pick up real keys from a developer
# `.env`. Individual tests opt in by setting them via monkeypatch.
for _var in (
    "LANGFUSE_SECRET_REF",
    "LANGFUSE_PUBLIC_REF",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_HOST",
    "LANGFUSE_BASE_URL",
    "LANGFUSE_REQUIRED",
):
    os.environ.pop(_var, None)


@pytest.fixture
def sample_billing_state():
    return {
        "query_id": "test-query-123",
        "query_text": "Why was I charged twice?",
        "messages": [],
        "classified_domain": "billing",
        "confidence_rationale": "Mentions charges",
        "current_node": "billing_agent",
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "test-run-456",
        "log_events": [],
    }


@pytest.fixture
def sample_retrieved_docs():
    return [
        {
            "content": "Our pricing plans include Basic ($9.99/mo), Professional ($29.99/mo), and Enterprise.",
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
