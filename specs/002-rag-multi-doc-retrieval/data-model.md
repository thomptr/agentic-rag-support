# Data Model: RAG Multi-Document Retrieval

**Branch**: `002-rag-multi-doc-retrieval` | **Date**: 2026-05-09

## LangGraph State Schema Extensions

The existing `SupportGraphState` is extended with new fields for multi-document retrieval. Existing fields are preserved for backward compatibility.

```python
from typing import Annotated, Literal
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


def _accumulate(a: list, b: list) -> list:
    return a + b


class SupportGraphState(TypedDict):
    """Shared state passed across all nodes in the support agent graph."""

    # --- Existing fields (from 001) ---
    query_id: str
    query_text: str
    messages: Annotated[list[BaseMessage], add_messages]
    classified_domain: Literal["billing", "technical", "account", "unknown"] | None
    confidence_rationale: str | None
    current_node: str | None
    retrieved_documents: list[dict] | None
    response_text: str | None
    citations: list[dict] | None
    run_id: str
    log_events: Annotated[list[dict], _accumulate]

    # --- New fields (002: multi-document retrieval) ---

    # Supervisor now classifies to one or more domains
    classified_domains: list[str] | None

    # Multi-query: generated search query variations
    search_queries: list[dict] | None
    # Each entry: { "query": str, "target_domain": str, "aspect": str }

    # Retrieval results before merge (raw results from all queries)
    raw_retrieval_results: Annotated[list[dict], _accumulate] | None

    # Merged, deduplicated, ranked results
    merged_results: list[dict] | None
    # Each entry: { "content": str, "metadata": dict, "score": float, "domain": str, "source_query": str }

    # Confidence assessment
    retrieval_confidence: dict | None
    # { "score": float, "result_count": int, "avg_similarity": float, "should_retry": bool, "reason": str }

    # Retry tracking
    retrieval_attempt: int
    max_retrieval_attempts: int

    # Policy gate (security_check) — present when the policy gate has run
    security_signals: list[dict] | None
    # Each entry: { "name": str, "matched_pattern": str, "severity": "info"|"warn"|"block", "action": str }

    escalation_required: bool | None
    escalation_reason: str | None
```

## Key Entities (from Spec)

### RetrievalPlan

Represented in state as the combination of `classified_domains` + `search_queries`. Not a separate database entity — lives in graph state only.

```python
# Example state after retrieval_planner node:
{
    "classified_domains": ["billing", "account"],
    "search_queries": [
        {"query": "double charge billing dispute", "target_domain": "billing", "aspect": "billing concern"},
        {"query": "account locked access issue", "target_domain": "account", "aspect": "access concern"},
        {"query": "charged twice account locked", "target_domain": "billing", "aspect": "combined query"},
    ]
}
```

### SearchQuery

A single search query derived from the original user question. Stored as a dict in `search_queries` list.

| Field | Type | Description |
|---|---|---|
| `query` | str | The reformulated search text |
| `target_domain` | str | Which domain to search ("billing", "technical", "account", or "all") |
| `aspect` | str | Which facet of the original question this query targets |

### RetrievalResultSet

The merged, deduplicated, ranked collection of documents. Stored as `merged_results` in state.

| Field | Type | Description |
|---|---|---|
| `content` | str | Document chunk text |
| `metadata` | dict | Original document metadata (domain, doc_id, title, chunk_index) |
| `score` | float | Similarity score from pgvector |
| `domain` | str | Domain this document belongs to (denormalized from metadata) |
| `source_query` | str | Which search query retrieved this document |

### ConfidenceAssessment

Evaluation of retrieval quality. Stored as `retrieval_confidence` in state.

| Field | Type | Description |
|---|---|---|
| `score` | float | Overall confidence score (0.0 - 1.0) |
| `result_count` | int | Number of results after dedup |
| `avg_similarity` | float | Average similarity score of top-k results |
| `should_retry` | bool | Whether retrieval should be retried |
| `reason` | str | Human-readable explanation of the assessment |

### SecuritySignal

A named policy signal raised by the `security_check` node. Stored as a list of dicts under `security_signals`.

| Field | Type | Description |
|---|---|---|
| `name` | str | Signal identifier (e.g. `account_takeover`, `fraud_suspected`, `pii_disclosure`) |
| `matched_pattern` | str | The rule or phrase that fired (used for audit / false-positive review) |
| `severity` | str | `"info"` (log only), `"warn"` (continue with hardened prompt), `"block"` (escalate, skip retrieval) |
| `action` | str | What the policy gate decided: `"continue"`, `"escalate"`, `"redact"` |

### EscalationOutcome

Materialized in state via `escalation_required: bool` plus `escalation_reason: str`, and emitted as a log event of type `escalation_triggered`. The terminal `escalation_handler` node consumes these to produce the user-facing routing response.

## PostgreSQL Schema

No new tables required. The existing schema is sufficient:

- **`langchain_pg_embedding`** (managed by langchain-postgres): Unchanged. Document chunks with domain metadata already support cross-domain queries via metadata filtering.
- **`observation_logs`**: Unchanged. New retrieval events (multi-query, retry attempts, confidence assessments) are logged as additional event types in the existing `event_data` JSONB column.

### New Observation Log Event Types

| event_type | event_data fields |
|---|---|
| `retrieval_plan` | `classified_domains`, `search_queries`, `query_count` |
| `multi_retrieval` | `attempt`, `queries_executed`, `total_results`, `unique_results`, `elapsed_ms` |
| `confidence_assessment` | `attempt`, `score`, `result_count`, `avg_similarity`, `should_retry`, `reason` |
| `retrieval_retry` | `attempt`, `previous_score`, `adjusted_params` |
| `knowledge_gap` | `final_attempt`, `final_score`, `reason` |
| `security_check` | `signals` (list of SecuritySignal), `action`, `latency_ms` |
| `escalation_triggered` | `signal_name`, `matched_pattern`, `reason`, `agent` |

## RAGAS Evaluation Dataset Schema

Evaluation datasets are stored as JSON files in `tests/evals/datasets/` (not in the database). Each entry represents a known question-answer pair with ground-truth context.

```python
# tests/evals/datasets/cross_domain.json
[
    {
        "question": "I was charged twice and now my account is locked",
        "ground_truth": "For duplicate charges, contact billing within 30 days for a refund. For locked accounts, verify identity through security questions or MFA reset.",
        "ground_truth_contexts": [
            "docs/knowledge_base/billing/payment-disputes.md",
            "docs/knowledge_base/account/login-procedures.md"
        ],
        "expected_domains": ["billing", "account"]
    }
]
```
