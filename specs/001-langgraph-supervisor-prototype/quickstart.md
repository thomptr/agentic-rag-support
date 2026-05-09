# Quickstart: LangGraph Supervisor Prototype

**Feature**: `001-langgraph-supervisor-prototype` | **Date**: 2026-05-08

## Prerequisites

- Python 3.11+
- Docker and Docker Compose
- An OpenAI API key (`OPENAI_API_KEY`) for LLM calls and embeddings
- [`uv`](https://docs.astral.sh/uv/) (recommended) or pip

## Setup

### 1. Environment variables

```bash
cp .env.example .env
# Edit .env and add your API keys:
#   OPENAI_API_KEY=sk-...
```

### 2. Start PostgreSQL (with pgvector)

```bash
make up
# or: docker compose up -d
```

This starts a Postgres 16 container with the pgvector extension on `localhost:5432`.

### 3. Install Python dependencies

Create a virtual environment and install dependencies using `uv`:

```bash
uv venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
```

If you don't have `uv` installed:

```bash
pip install uv
```

Or install it system-wide via the standalone installer (no Python required):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 4. Seed the knowledge base

```bash
make seed
# or: python -m src.rag.ingest
```

This reads markdown documents from `docs/knowledge_base/{billing,technical,account}/`, chunks them, generates embeddings via OpenAI, and stores them in pgvector.

### 5. Start the API server

```bash
make run
# or: uvicorn src.api.main:app --reload
```

The server starts on `http://localhost:8000`.

## Usage

### Submit a query

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query_text": "Why was I charged twice this month?"}'
```

### Check service health

```bash
curl http://localhost:8000/health
```

## Running Tests

```bash
# Unit tests (no external dependencies)
make test-unit

# Integration tests (requires running Postgres)
make test-int

# All tests
make test
```

## Teardown

```bash
make down
# or: docker compose down
```

Add `-v` to remove the Postgres data volume: `docker compose down -v`
