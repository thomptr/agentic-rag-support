# Implementation Plan: LangGraph Supervisor Prototype

**Branch**: `001-langgraph-supervisor-prototype` | **Date**: 2026-05-08 | **Spec**: `specs/001-langgraph-supervisor-prototype/spec.md`

## Summary

Build a local LangGraph-based supervisor agent that classifies customer support queries into billing, technical, or account domains and routes them to the appropriate worker agent. Each worker retrieves context from a pgvector-backed knowledge base before generating a grounded response. The system runs locally via Docker Compose (Postgres) and a FastAPI service layer, with full structured observability logging.

## Technical Context

| Dimension | Decision |
|---|---|
| **Language/Version** | Python 3.11+ |
| **Primary Dependencies** | `langgraph`, `langchain-anthropic`, `langchain-postgres`, `langchain-openai`, `fastapi`, `uvicorn`, `psycopg[binary]` |
| **LLM** | Claude via `langchain-anthropic` `ChatAnthropic` (wraps the Anthropic SDK) |
| **Embeddings** | OpenAI `text-embedding-3-small` via `langchain-openai` |
| **Vector Store** | PostgreSQL 16 with pgvector extension, accessed via `langchain-postgres` `PGVectorStore` |
| **Relational Store** | Same PostgreSQL instance (observation log table) |
| **Service Layer** | FastAPI (POST /query, GET /health) |
| **Infrastructure** | Docker Compose (Postgres with pgvector in container; app runs on host) |
| **Testing** | pytest with pytest-asyncio |
| **Observability** | Structured JSON logging (`structlog`) to stdout |
| **Environment** | `.env` files via `python-dotenv`; secrets never committed |
| **Project Type** | Local service (FastAPI + optional CLI entry point) |
| **Performance Goals** | < 30s end-to-end per query (SC-003) |

### ChatAnthropic vs Raw Anthropic SDK

The constitution states "Claude via the Anthropic SDK." `langchain-anthropic`'s `ChatAnthropic` wraps the official SDK internally, providing native LangGraph `StateGraph` compatibility, structured output for classification, and tool-calling integration without custom adapter code. This satisfies both the constitution and Principle V (Simplicity).

## Constitution Check

| Principle | Status | Notes |
|---|---|---|
| **I. RAG-First** | PASS | FR-004/FR-005: every worker calls retriever before LLM. Tests assert non-empty citations on every response. |
| **II. Agentic Autonomy** | PASS | LangGraph state graph supports multi-step reasoning. Tool use beyond RAG retrieval is out of scope for this POC. |
| **III. Test-First** | PASS | TDD enforced: write tests → confirm fail → implement. Every implementation task begins with its test. |
| **IV. Observability** | PASS | `structlog` emits JSON-lines for every LLM call (model, tokens, latency) and retrieval call (query, top-k, scores, elapsed). All routing decisions logged. |
| **V. Simplicity** | PASS | Only 3 workers (no product/retention). No tools beyond RAG. Docker Compose for Postgres only. FastAPI is minimal (2 endpoints). Three similar worker functions preferred over a factory abstraction. |

### Complexity Tracking

| Potential Violation | Decision | Justification |
|---|---|---|
| `langchain-postgres` instead of raw SQL+pgvector | ACCEPTED | Avoids reimplementing vector search, embedding storage, and retrieval. Raw SQL would be more error-prone. |
| `structlog` instead of stdlib `logging` | ACCEPTED | Constitution requires structured JSON output. `structlog` produces JSON natively; stdlib requires custom formatters. |
| FastAPI instead of CLI-only | ACCEPTED | User's explicit choice. Satisfies FR-012 (runnable locally via `uvicorn`). |

## Phase 0: Research Decisions

| Decision | Resolution | Rationale |
|---|---|---|
| Vector store | PostgreSQL 16 + pgvector | User decision. Single DB for vectors and relational data. |
| Embedding model | OpenAI `text-embedding-3-small` | User decision. Cheap ($0.02/1M tokens), widely used, good quality. |
| LLM integration | `ChatAnthropic` from `langchain-anthropic` | Wraps Anthropic SDK. Native LangGraph compatibility. |
| LangGraph approach | Custom `StateGraph` (not `create_supervisor`) | Hand-built graph gives full control over routing logic, observability, and RAG-first worker behavior. |
| Docker Compose | Postgres container only; app on host | Simplest setup. Avoids Docker networking complexity. |
| State schema | `TypedDict` with `Annotated` reducers | LangGraph standard. Simple, type-checked. |

## Phase 1: Data Model

### LangGraph State Schema

```python
class SupportGraphState(TypedDict):
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
    log_events: Annotated[list[dict], lambda a, b: a + b]
```

### PostgreSQL Schema

**Vector layer** (managed by `langchain-postgres` PGVectorStore): `langchain_pg_embedding` table (auto-created) storing document chunks as vectors with metadata (domain, doc_id, title).

**Relational layer** (application-managed):

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS observation_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_observation_logs_run_id ON observation_logs(run_id);
CREATE INDEX idx_observation_logs_event_type ON observation_logs(event_type);
```

## Phase 1: Contracts

### FastAPI Endpoints

**POST /query**
```
Request:  { "query_text": str, "session_id": str | None }
Response: { "query_id": str, "response_text": str, "agent": str,
            "routing_rationale": str, "citations": [...],
            "metadata": { "classified_domain": str, "run_id": str,
                          "total_latency_ms": float, "llm_calls": int,
                          "retrieval_calls": int } }
```

**GET /health**
```
Response: { "status": "healthy", "database": "connected"|"disconnected",
            "vector_store": "ready"|"not_ready", "llm": "configured"|"not_configured" }
```

### Agent Node Signatures

```python
def supervisor(state: SupportGraphState) -> Command:
    # Classify query → return Command(goto=<agent_node>)

def billing_agent(state: SupportGraphState) -> dict:
    # Retrieve docs → generate grounded response → return state updates

def route_query(state: SupportGraphState) -> str:
    # Map classified_domain → node name
```

## Source Code Structure

```
agentic-rag-support/
├── pyproject.toml
├── docker-compose.yml
├── .env.example
├── Makefile
├── scripts/
│   └── init.sql                      # CREATE EXTENSION vector
│
├── src/
│   ├── __init__.py
│   ├── config.py                     # Settings from .env (pydantic-settings)
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── supervisor.py             # Classification + routing
│   │   ├── billing_agent.py          # Billing domain worker
│   │   ├── technical_agent.py        # Technical domain worker
│   │   ├── account_agent.py          # Account domain worker
│   │   └── fallback.py              # Unclassifiable queries
│   │
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py                  # SupportGraphState TypedDict
│   │   ├── workflow.py               # StateGraph construction + compile
│   │   └── routing.py                # Conditional edge logic
│   │
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── retriever.py              # PGVectorStore wrapper
│   │   ├── ingest.py                 # Load + chunk + embed seed docs
│   │   └── chunking.py               # Text splitting
│   │
│   ├── observability/
│   │   ├── __init__.py
│   │   └── logger.py                 # structlog config + helpers
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI app + routes
│   │   └── schemas.py                # Pydantic request/response models
│   │
│   └── db/
│       ├── __init__.py
│       └── connection.py             # Postgres connection + pgvector init
│
├── docs/
│   └── knowledge_base/
│       ├── billing/                   # 3-5 sample docs (markdown)
│       ├── technical/                 # 3-5 sample docs (markdown)
│       └── account/                   # 3-5 sample docs (markdown)
│
├── tests/
│   ├── conftest.py                   # Shared fixtures
│   ├── unit/
│   │   ├── test_state.py
│   │   ├── test_routing.py
│   │   ├── test_chunking.py
│   │   ├── test_supervisor.py
│   │   ├── test_billing_agent.py
│   │   ├── test_technical_agent.py
│   │   ├── test_account_agent.py
│   │   ├── test_fallback.py
│   │   └── test_logger.py
│   ├── integration/
│   │   ├── test_retriever.py
│   │   ├── test_ingest.py
│   │   ├── test_workflow.py
│   │   └── test_api.py
│   └── evals/
│       └── test_routing_accuracy.py  # 9+ queries, assert ≥90% (SC-001)
│
└── specs/                            # Existing
    └── 001-langgraph-supervisor-prototype/
```

## LangGraph Supervisor Graph

```
START → supervisor → [conditional edge] → billing_agent  ─┐
                                        → technical_agent ─┤→ END
                                        → account_agent  ─┘
                                        → fallback_handler → END
```

- **Supervisor**: Calls Claude with structured output to classify domain. Writes `classified_domain` and `confidence_rationale` to state. Returns `Command(goto=...)`.
- **Workers**: (1) Call retriever with query text filtered by domain, (2) receive top-k chunks with scores, (3) prompt Claude with retrieved context to generate grounded answer with citations, (4) write `response_text`, `citations`, and log events to state.
- **Fallback**: Returns acknowledgement without retrieval. Logs event.
- **Single pgvector collection** with `domain` metadata field for filtering (simpler than per-domain collections).

## Docker Compose

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: agentic_rag
      POSTGRES_PASSWORD: agentic_rag_dev
      POSTGRES_DB: agentic_rag
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./scripts/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agentic_rag"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

## Observability Log Events

All events share `run_id` and `timestamp`:

- **llm_call** (FR-008): `agent`, `model`, `prompt_hash`, `input_tokens`, `output_tokens`, `latency_ms`
- **retrieval** (FR-009): `agent`, `query`, `top_k`, `results` (doc_id, score, preview), `elapsed_ms`
- **routing_decision** (FR-010): `query_text`, `classified_domain`, `confidence_rationale`, `routed_to`
- **agent_response** (FR-010): `agent`, `response_length`, `citation_count`

Helpers in `observability/logger.py`: `log_llm_call()`, `log_retrieval()`, `log_routing_decision()`, `log_agent_response()`. Each emits a structlog line AND appends to state `log_events`.

## Implementation Sequence (TDD)

Each step: write test (RED) → confirm fail → implement (GREEN).

1. **Scaffolding**: `pyproject.toml`, `docker-compose.yml`, `.env.example`, `Makefile`, `src/` packages
2. **State schema**: `test_state.py` → `graph/state.py`
3. **Observability**: `test_logger.py` → `observability/logger.py`
4. **DB connection**: `db/connection.py` (tested via integration tests)
5. **Chunking**: `test_chunking.py` → `rag/chunking.py`
6. **Ingestion**: `test_ingest.py` → `rag/ingest.py` + seed docs in `docs/knowledge_base/`
7. **Retriever**: `test_retriever.py` → `rag/retriever.py`
8. **Routing logic**: `test_routing.py` → `graph/routing.py`
9. **Supervisor**: `test_supervisor.py` → `agents/supervisor.py`
10. **Workers**: `test_billing_agent.py` → `agents/billing_agent.py` (repeat for technical, account)
11. **Fallback**: `test_fallback.py` → `agents/fallback.py`
12. **Graph workflow**: `test_workflow.py` → `graph/workflow.py`
13. **API layer**: `test_api.py` → `api/main.py` + `api/schemas.py`
14. **Config**: `config.py` (tested implicitly)
15. **Eval suite**: `test_routing_accuracy.py` (real LLM, validates SC-001)

## Dependencies (pyproject.toml)

```toml
[project]
name = "agentic-rag-support"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "langgraph>=0.4",
    "langchain-anthropic>=0.3",
    "langchain-postgres>=0.0.14",
    "langchain-openai>=0.3",
    "langchain-core>=0.3",
    "langchain-text-splitters>=0.3",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "psycopg[binary]>=3.2",
    "structlog>=24.0",
    "python-dotenv>=1.0",
    "pydantic-settings>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "httpx>=0.27",
    "pytest-cov>=6.0",
]
```

## Environment Variables (.env.example)

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql+psycopg://agentic_rag:agentic_rag_dev@localhost:5432/agentic_rag
LLM_MODEL=claude-sonnet-4-20250514
EMBEDDING_MODEL=text-embedding-3-small
LOG_LEVEL=INFO
```

## Makefile

```makefile
up:       docker compose up -d
down:     docker compose down
seed:     python -m src.rag.ingest
test:     pytest tests/
test-unit: pytest tests/unit/
test-int: pytest tests/integration/
run:      uvicorn src.api.main:app --reload
all:      make up && make seed && make run
```

## Conflict Resolutions

| Conflict | Resolution |
|---|---|
| Spec assumes ChromaDB/FAISS | Replaced with PostgreSQL + pgvector per user decision. Spec anticipated this ("TBD during planning"). |
| Constitution vector store TBD | Resolved as Postgres + pgvector. Constitution's "TBD during Phase 0" language anticipated this. |
| Layout includes product/retention agents | Removed -- out of scope per spec. |
| Layout includes tools/ directory | Removed -- no tools beyond RAG retrieval for this POC. |
| Spec says CLI-only | FastAPI added per user's explicit choice. Still locally runnable (satisfies FR-012). |

## Verification

1. `make up` -- Postgres container starts, pgvector extension loaded
2. `make seed` -- Knowledge base documents ingested into pgvector
3. `make test-unit` -- All unit tests pass (mocked dependencies)
4. `make test-int` -- Integration tests pass (real Postgres, mocked LLM)
5. `make run` -- FastAPI starts on localhost:8000
6. `curl -X POST localhost:8000/query -d '{"query_text":"Why was I charged twice?"}'` -- Returns grounded response from billing agent with citations
7. `curl localhost:8000/health` -- Returns healthy status
8. Structured JSON logs visible in stdout during all operations
