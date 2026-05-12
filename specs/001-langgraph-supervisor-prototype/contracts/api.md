# API Contract: LangGraph Supervisor Prototype

**Feature**: `001-langgraph-supervisor-prototype` | **Date**: 2026-05-08

## Base URL

```
http://localhost:8000
```

## Endpoints

### POST /query

Submit a customer support query for classification and grounded response.

**Request**:
```json
{
    "query_text": "Why was I charged twice this month?",
    "session_id": null
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `query_text` | string | Yes | The customer's support question. Max 10,000 chars. |
| `session_id` | string | No | Optional session identifier for future multi-turn support. |

**Response (200 OK)**:
```json
{
    "query_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "response_text": "Based on our billing documentation, duplicate charges can occur when...",
    "agent": "billing_agent",
    "routing_rationale": "Query explicitly mentions charges and billing discrepancy",
    "citations": [
        {
            "doc_id": "f1e2d3c4-b5a6-7890-dcba-fedcba098765",
            "chunk_text": "Duplicate charges may appear when a payment is retried after a timeout...",
            "score": 0.89
        }
    ],
    "metadata": {
        "classified_domain": "billing",
        "run_id": "11223344-5566-7788-99aa-bbccddeeff00",
        "total_latency_ms": 4250.3,
        "llm_calls": 2,
        "retrieval_calls": 1
    }
}
```

| Field | Type | Description |
|---|---|---|
| `query_id` | string (UUID) | Unique identifier for this query |
| `response_text` | string | The grounded answer from the worker agent |
| `agent` | string | Which agent handled the query (`billing_agent`, `technical_agent`, `account_agent`, `fallback`) |
| `routing_rationale` | string | Supervisor's reasoning for routing to this agent |
| `citations` | array | Source references from the knowledge base |
| `citations[].doc_id` | string (UUID) | Knowledge base document identifier |
| `citations[].chunk_text` | string | The specific text passage cited |
| `citations[].score` | float | Cosine similarity score (0.0 - 1.0) |
| `metadata.classified_domain` | string | The domain classification (`billing`, `technical`, `account`, `unknown`) |
| `metadata.run_id` | string (UUID) | Trace ID for correlating log events |
| `metadata.total_latency_ms` | float | End-to-end processing time |
| `metadata.llm_calls` | int | Number of LLM invocations in this run |
| `metadata.retrieval_calls` | int | Number of vector search queries in this run |

**Response (422 Unprocessable Entity)**:
```json
{
    "detail": [
        {
            "loc": ["body", "query_text"],
            "msg": "Field required",
            "type": "missing"
        }
    ]
}
```

**Response (500 Internal Server Error)**:
```json
{
    "detail": "An internal error occurred. Check run_id in logs for details.",
    "run_id": "11223344-5566-7788-99aa-bbccddeeff00"
}
```

### GET /health

Health check endpoint for infrastructure monitoring.

**Response (200 OK)**:
```json
{
    "status": "healthy",
    "database": "connected",
    "vector_store": "ready",
    "llm": "configured"
}
```

| Field | Type | Values | Description |
|---|---|---|---|
| `status` | string | `healthy` / `unhealthy` | Overall service status |
| `database` | string | `connected` / `disconnected` | PostgreSQL connection status |
| `vector_store` | string | `ready` / `not_ready` | pgvector collection availability |
| `llm` | string | `configured` / `not_configured` | Whether `ANTHROPIC_API_KEY` is set |

## Agent Interface Contract

Each agent is a LangGraph node function with the following contract:

### Supervisor Node

```python
def supervisor(state: SupportGraphState) -> Command:
    """
    Input state:
        - query_text: str (the customer's question)
        - run_id: str (trace identifier)

    Behavior:
        1. Call Claude with structured output to classify domain
        2. Log routing decision via log_routing_decision()
        3. Return Command(goto=<target_node>)

    State writes:
        - classified_domain: "billing" | "technical" | "account" | "unknown"
        - confidence_rationale: str
        - current_node: str
        - log_events: appended with routing_decision event
    """
```

### Worker Node (billing/technical/account)

```python
def billing_agent(state: SupportGraphState) -> dict:
    """
    Input state:
        - query_text: str
        - classified_domain: str
        - run_id: str

    Behavior:
        1. Retrieve top-k documents from pgvector filtered by domain
        2. Log retrieval via log_retrieval()
        3. Call Claude with retrieved context to generate grounded response
        4. Log LLM call via log_llm_call()
        5. Extract citations from retrieved documents

    State writes:
        - retrieved_documents: list[dict]
        - response_text: str
        - citations: list[dict] (MUST be non-empty)
        - log_events: appended with retrieval + llm_call + agent_response events

    Invariant: citations MUST NOT be empty (RAG-first principle).
    """
```

### Fallback Node

```python
def fallback_handler(state: SupportGraphState) -> dict:
    """
    Input state:
        - query_text: str
        - classified_domain: "unknown"
        - run_id: str

    Behavior:
        1. Generate a fallback response acknowledging inability to route
        2. Log fallback event

    State writes:
        - response_text: str (acknowledgement message)
        - citations: [] (empty -- no retrieval for fallback)
        - log_events: appended with agent_response event
    """
```

## Observability Event Contract

All log events emitted to stdout as JSON lines. Each event includes:

| Field | Type | Present In |
|---|---|---|
| `event_type` | string | All events |
| `run_id` | string (UUID) | All events |
| `timestamp` | string (ISO 8601) | All events |
| `agent` | string | llm_call, retrieval, agent_response |
| `model` | string | llm_call |
| `prompt_hash` | string | llm_call |
| `input_tokens` | int | llm_call |
| `output_tokens` | int | llm_call |
| `latency_ms` | float | llm_call, retrieval |
| `query` | string | retrieval |
| `top_k` | int | retrieval |
| `results` | array | retrieval |
| `classified_domain` | string | routing_decision |
| `confidence_rationale` | string | routing_decision |
| `routed_to` | string | routing_decision |
| `response_length` | int | agent_response |
| `citation_count` | int | agent_response |
