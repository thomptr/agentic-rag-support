# API Contracts: RAG Multi-Document Retrieval

**Branch**: `002-rag-multi-doc-retrieval` | **Date**: 2026-05-09

## POST /query (Updated)

The existing endpoint is extended with multi-domain retrieval metadata. The request schema is unchanged.

### Request

```json
{
  "query_text": "I was charged twice and now my account is locked",
  "session_id": "optional-session-id"
}
```

### Response

```json
{
  "query_id": "uuid",
  "response_text": "For the duplicate charge, you can request a refund within 30 days by contacting billing support. Regarding your locked account, you can regain access by...",
  "agent": "response_generator",
  "routing_rationale": "Query spans billing (duplicate charge) and account (locked access) domains",
  "citations": [
    {
      "content": "Customers may dispute charges within 30 days...",
      "domain": "billing",
      "source": "payment-disputes.md",
      "score": 0.92
    },
    {
      "content": "If your account is locked, verify your identity...",
      "domain": "account",
      "source": "login-procedures.md",
      "score": 0.89
    }
  ],
  "metadata": {
    "classified_domains": ["billing", "account"],
    "run_id": "uuid",
    "total_latency_ms": 4200.5,
    "llm_calls": 3,
    "retrieval_calls": 2,
    "retrieval_attempts": 1,
    "documents_retrieved": 8,
    "documents_after_dedup": 6,
    "retrieval_confidence": 0.87
  }
}
```

### Response Field Changes from 001

| Field | Change | Description |
|---|---|---|
| `metadata.classified_domains` | **New** | List of domains the query was classified into |
| `metadata.retrieval_attempts` | **New** | Number of retrieval attempts (1 = no retry) |
| `metadata.documents_retrieved` | **New** | Total documents retrieved across all queries |
| `metadata.documents_after_dedup` | **New** | Documents after deduplication |
| `metadata.retrieval_confidence` | **New** | Confidence score of final retrieval results |
| `citations[].domain` | **New** | Domain each cited document belongs to |
| `citations[].score` | **New** | Similarity score for the cited document |
| `agent` | **Changed** | Now returns `"response_generator"` instead of domain-specific agent name |

### Knowledge Gap Response

When retrieval confidence remains low after all retry attempts:

```json
{
  "query_id": "uuid",
  "response_text": "I don't have enough information in my knowledge base to fully answer your question about [topic]. I'd recommend contacting a human support agent for assistance.",
  "agent": "response_generator",
  "routing_rationale": "Query classified to [domains] but retrieval confidence remained below threshold after 3 attempts",
  "citations": [],
  "metadata": {
    "classified_domains": ["technical"],
    "run_id": "uuid",
    "total_latency_ms": 8500.0,
    "llm_calls": 2,
    "retrieval_calls": 3,
    "retrieval_attempts": 3,
    "documents_retrieved": 4,
    "documents_after_dedup": 3,
    "retrieval_confidence": 0.25
  }
}
```

## GET /health (Unchanged)

```json
{
  "status": "healthy",
  "database": "connected",
  "vector_store": "ready",
  "llm": "configured"
}
```

## Graph Node Contracts

### supervisor

```python
def supervisor(state: SupportGraphState) -> Command:
    """Classify query into one or more domains.

    Reads: query_text, run_id
    Writes: classified_domain, classified_domains, confidence_rationale, log_events
    Returns: Command(goto="retrieval_planner") or Command(goto="fallback_handler")
    """
```

### retrieval_planner

```python
def retrieval_planner(state: SupportGraphState) -> dict:
    """Generate search query variations targeting classified domains.

    Reads: query_text, classified_domains, run_id
    Writes: search_queries, retrieval_attempt, max_retrieval_attempts, log_events
    """
```

### multi_retriever

```python
def multi_retriever(state: SupportGraphState) -> dict:
    """Execute search queries across domains, deduplicate, and rank results.

    Reads: search_queries, retrieval_attempt, run_id
    Writes: raw_retrieval_results, merged_results, retrieved_documents, log_events
    """
```

### confidence_check

```python
def confidence_check(state: SupportGraphState) -> Command:
    """Evaluate retrieval quality and decide whether to retry or proceed.

    Reads: merged_results, retrieval_attempt, max_retrieval_attempts, run_id
    Writes: retrieval_confidence, log_events
    Returns: Command(goto="multi_retriever") for retry, Command(goto="response_generator") to proceed
    """
```

### response_generator

```python
def response_generator(state: SupportGraphState) -> dict:
    """Generate a grounded response with citations from merged retrieval results.

    Reads: query_text, merged_results, retrieval_confidence, classified_domains, run_id
    Writes: response_text, citations, routed_to_agent, log_events
    """
```

### validate_response (Existing, Updated)

```python
def validate_response(state: SupportGraphState) -> dict:
    """Validate response has citations and meets quality bar.

    Reads: response_text, citations, retrieval_confidence, run_id
    Writes: log_events
    """
```
