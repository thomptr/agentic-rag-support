# Data Model: LangGraph Supervisor Prototype

**Feature**: `001-langgraph-supervisor-prototype` | **Date**: 2026-05-08

## Entities

### CustomerQuery

The inbound support request submitted by a user.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| query_id | UUID | PK, auto-generated | Assigned at API entry point |
| query_text | str | Required, non-empty | The customer's question |
| session_id | str | Optional | Reserved for future multi-turn support |
| created_at | datetime | Auto-set | Timestamp of submission |

**Validation**: `query_text` must be non-empty and under 10,000 characters.

### RoutingDecision

The supervisor agent's classification output.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| query_id | UUID | FK to CustomerQuery | Links to the originating query |
| classified_domain | enum | "billing" / "technical" / "account" / "unknown" | LLM classification result |
| confidence_rationale | str | Required | LLM's reasoning for classification |
| routed_to_agent | str | Required | Node name the query was routed to |
| created_at | datetime | Auto-set | Timestamp of routing decision |

**State transitions**: `unknown` triggers the fallback handler instead of a worker agent.

### AgentResponse

The worker agent's grounded answer.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| query_id | UUID | FK to CustomerQuery | Links to the originating query |
| agent_name | str | Required | "billing_agent" / "technical_agent" / "account_agent" / "fallback" |
| response_text | str | Required | The generated answer |
| citations | list[Citation] | Must be non-empty for workers | Source references (empty only for fallback) |
| created_at | datetime | Auto-set | Timestamp of response |

**Validation**: Workers MUST have at least one citation (RAG-first principle). Fallback handler is exempt.

### KnowledgeDocument

Source documents stored in pgvector for RAG retrieval.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| doc_id | UUID | PK, auto-generated | Stable identifier across re-ingestions |
| domain | str | "billing" / "technical" / "account" | Used for metadata filtering in retrieval |
| title | str | Required | Document title for citation display |
| content | str | Required | Full document text (pre-chunking) |
| source_file | str | Required | Path to the original markdown file |
| created_at | datetime | Auto-set | Ingestion timestamp |

**Note**: Documents are chunked during ingestion. The `langchain_pg_embedding` table (managed by PGVectorStore) stores the individual chunks with their vector embeddings and metadata linking back to the source document.

### Citation

A reference from an agent response to a source document chunk.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| doc_id | UUID | FK to KnowledgeDocument | Source document identifier |
| chunk_text | str | Required | The specific text passage cited |
| similarity_score | float | 0.0 - 1.0 | Cosine similarity score from pgvector |

## Relationships

```
CustomerQuery 1──1 RoutingDecision
CustomerQuery 1──1 AgentResponse
AgentResponse 1──* Citation
Citation *──1 KnowledgeDocument (chunk)
```

## Storage Strategy

### In LangGraph State (runtime only)

All entities above live in the `SupportGraphState` TypedDict during a single graph execution. They are not persisted to relational tables for this POC. The full state is returned to the FastAPI endpoint after graph completion, which constructs the API response.

### In PostgreSQL (persisted)

| Table | Managed By | Purpose |
|---|---|---|
| `langchain_pg_embedding` | `langchain-postgres` PGVectorStore | Document chunks + vector embeddings |
| `langchain_pg_collection` | `langchain-postgres` PGVectorStore | Collection metadata |
| `observation_logs` | Application code | Structured log events for replay/audit |

### pgvector Configuration

- **Extension**: `vector` (enabled via `scripts/init.sql`)
- **Embedding dimensions**: 1536 (OpenAI `text-embedding-3-small`)
- **Distance metric**: Cosine similarity (default for `langchain-postgres`)
- **Collection**: Single collection `support_kb` with `domain` metadata field for filtering
- **Top-k**: 5 documents per retrieval call

## LangGraph State Schema

```python
from typing import TypedDict, Annotated, Literal
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage

class SupportGraphState(TypedDict):
    """Shared state across all nodes in the support agent graph."""
    # Core query
    query_id: str
    query_text: str

    # Message history (LangGraph convention)
    messages: Annotated[list[BaseMessage], add_messages]

    # Routing
    classified_domain: Literal["billing", "technical", "account", "unknown"] | None
    confidence_rationale: str | None
    routed_to_agent: str | None

    # Retrieval
    retrieved_documents: list[dict] | None  # [{content, metadata, score}]

    # Response
    response_text: str | None
    citations: list[dict] | None  # [{doc_id, chunk_text, score}]

    # Observability
    run_id: str
    log_events: Annotated[list[dict], lambda a, b: a + b]
```

## PostgreSQL DDL

```sql
-- Run on container initialization (scripts/init.sql)
CREATE EXTENSION IF NOT EXISTS vector;

-- Observation log for structured event replay
CREATE TABLE IF NOT EXISTS observation_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL,
    event_type VARCHAR(50) NOT NULL,  -- 'llm_call', 'retrieval', 'routing_decision', 'agent_response'
    event_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_observation_logs_run_id ON observation_logs(run_id);
CREATE INDEX idx_observation_logs_event_type ON observation_logs(event_type);

-- The langchain_pg_embedding and langchain_pg_collection tables
-- are auto-created by PGVectorStore on first use.
```
