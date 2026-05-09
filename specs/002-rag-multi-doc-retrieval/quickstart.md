# Quickstart: RAG Multi-Document Retrieval

**Prerequisite**: Complete 001-langgraph-supervisor-prototype setup (Postgres running, knowledge base seeded).

## 1. Install New Dependencies

```bash
pip install -e ".[dev]"
```

This picks up the new `ragas` dependency added to `pyproject.toml`.

## 2. Verify Existing Setup

```bash
make up          # Ensure Postgres is running
make seed        # Ensure knowledge base is seeded (idempotent)
make test-unit   # Existing tests still pass
```

## 3. Run the Updated System

```bash
make run         # Start FastAPI on localhost:8000
```

## 4. Test Cross-Domain Query

```bash
curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query_text": "I was charged twice and now my account is locked"}' | python -m json.tool
```

Expected: response with citations from both `billing` and `account` domains, `classified_domains: ["billing", "account"]`.

## 5. Test Adaptive Retrieval

```bash
curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query_text": "How do I configure webhook retry policies for failed event deliveries?"}' | python -m json.tool
```

Expected: system detects low-confidence results, retries with broader parameters, and either finds relevant docs or acknowledges the knowledge gap.

## 6. Run RAGAS Evaluation

```bash
pytest tests/evals/test_rag_quality.py -v
```

This runs the RAGAS evaluation suite, asserting that faithfulness, answer relevancy, context precision, and context recall meet minimum thresholds.

## 7. Run Full Test Suite

```bash
make test        # All tests (unit + integration + evals)
```

## Key Makefile Targets

| Target | Description |
|---|---|
| `make test` | Run all tests |
| `make test-unit` | Unit tests only (mocked dependencies) |
| `make test-int` | Integration tests (requires Postgres) |
| `make test-evals` | Evaluation tests (requires LLM API keys) |
| `make up` | Start Postgres container |
| `make seed` | Ingest knowledge base documents |
| `make run` | Start FastAPI server |
