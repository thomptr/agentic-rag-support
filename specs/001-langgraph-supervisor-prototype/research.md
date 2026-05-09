# Research: LangGraph Supervisor Prototype

**Feature**: `001-langgraph-supervisor-prototype` | **Date**: 2026-05-08

## Vector Store

- **Decision**: PostgreSQL 16 with pgvector extension
- **Rationale**: User requirement. Single database for both vector embeddings and relational data (observation logs). Eliminates the need for a separate vector store service. pgvector supports cosine similarity, inner product, and L2 distance operators. The `pgvector/pgvector:pg16` Docker image provides a ready-to-use Postgres instance with the extension pre-installed.
- **Alternatives considered**:
  - ChromaDB: Lightweight, easy to set up, but adds a separate service. No relational data support.
  - FAISS: In-memory only (no persistence without custom serialization). No relational data support. Not suitable for a service that restarts.

## Embedding Model

- **Decision**: OpenAI `text-embedding-3-small` via `langchain-openai`
- **Rationale**: User decision. Cheap at $0.02/1M tokens, widely used, strong retrieval quality for the price. 1536 dimensions. Well-supported by `langchain-openai` and `langchain-postgres` PGVectorStore.
- **Alternatives considered**:
  - Voyage AI `voyage-3-lite`: Anthropic's partner. Free tier (200M tokens). Better alignment with the "Claude ecosystem" but adds another vendor relationship.
  - Local sentence-transformers: No API key needed but lower quality and slower on CPU. Adds PyTorch as a heavy dependency.

## LLM Integration

- **Decision**: `ChatAnthropic` from `langchain-anthropic` (wraps Anthropic SDK)
- **Rationale**: The constitution mandates "Claude via the Anthropic SDK." `ChatAnthropic` wraps the official SDK internally while providing native LangGraph compatibility: message passing, structured output via `with_structured_output()`, and tool-calling. Using the raw Anthropic SDK would require building custom LangGraph node adapters.
- **Alternatives considered**:
  - Raw `anthropic` SDK: Maximum control but requires custom adapters for LangGraph's message types, structured output parsing, and state management. Violates Principle V (Simplicity) for no added benefit.

## LangGraph Architecture

- **Decision**: Custom `StateGraph` with hand-built nodes (not `create_supervisor` or `create_react_agent`)
- **Rationale**: The high-level `create_supervisor` helper abstracts away routing logic and makes it difficult to: (a) enforce RAG-first behavior in workers, (b) emit fine-grained observability events at each decision point, and (c) implement custom fallback handling. A hand-built `StateGraph` gives full visibility and control over every node transition.
- **Alternatives considered**:
  - `langgraph.prebuilt.create_supervisor`: Convenient but hides routing decisions inside the library. Cannot enforce that workers always retrieve before generating. Observability hooks are limited.
  - `create_react_agent` per worker: Overkill for this POC where workers have a fixed two-step flow (retrieve then generate). ReAct loops add unnecessary complexity.

## State Schema Pattern

- **Decision**: `TypedDict` with `Annotated` reducers
- **Rationale**: LangGraph's standard pattern. `TypedDict` provides type checking without runtime overhead. `Annotated` reducers (e.g., `add_messages` for message lists, custom lambda for log accumulation) handle state merging at graph edges. No Pydantic overhead needed for internal state.
- **Alternatives considered**:
  - Pydantic `BaseModel`: Adds validation overhead on every state transition. Useful for external APIs (and used in FastAPI schemas) but unnecessary for internal graph state.
  - Plain dict: No type checking. Easy to introduce typos in key names.

## Docker Compose Strategy

- **Decision**: Postgres container only; Python app runs on host
- **Rationale**: Simplest approach for local development. Avoids Docker networking complexity (the app connects to `localhost:5432`). Developers can use their local Python environment with hot-reload (`uvicorn --reload`). The Postgres container is stateless (data persists in a named volume).
- **Alternatives considered**:
  - Full containerization (app + Postgres): Adds Dockerfile for the app, Docker networking, and makes debugging harder (no hot-reload without bind mounts). Unnecessary complexity for a POC.

## Observability Library

- **Decision**: `structlog` for structured JSON logging to stdout
- **Rationale**: Constitution Principle IV requires structured logging. `structlog` outputs JSON lines natively with zero configuration beyond initial setup. It integrates with Python's stdlib logging so third-party library logs are also captured. Lightweight dependency.
- **Alternatives considered**:
  - stdlib `logging` with custom JSON formatter: Requires writing and maintaining a custom formatter class. More code for the same result.
  - OpenTelemetry: Production-grade observability but massive dependency tree. Violates Principle V for a POC.
