# Quickstart: Agent Business Action Tools

**Feature**: 003-agent-action-tools | **Date**: 2026-05-09

## Prerequisites

- Python 3.11+
- PostgreSQL 16 with pgvector (existing from 001/002)
- `.env` file with `OPENAI_API_KEY` and `DATABASE_URL` configured

## Setup

```bash
# Install dependencies (no new packages required beyond existing pyproject.toml)
pip install -e ".[dev]"

# Start the API server
uvicorn src.api.main:app --reload
```

## Try It Out

### 1. Order Status Lookup (read-only — executes autonomously)

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query_text": "What is the status of my order ORD-12345?"}'
```

**Expected**: The agent retrieves relevant KB articles, then calls `order_status_lookup` autonomously. The response includes the order status ("shipped") along with retrieval-based context.

### 2. Support Ticket Creation (low-risk — executes autonomously)

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query_text": "I have been having issues with my billing. Can you create a support ticket for me?"}'
```

**Expected**: The agent creates a ticket via `create_support_ticket` and returns the ticket ID.

### 3. Refund Request (high-risk — requires human approval)

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query_text": "I need a refund for order ORD-12345, the product was defective."}'
```

**Expected**: The agent identifies this as a refund action, prepares it, but does NOT execute. The response says the request is pending review and includes an `approval_id`.

### 4. Approve the Refund

```bash
# List pending approvals
curl http://localhost:8000/approvals

# Approve the refund
curl -X POST http://localhost:8000/approvals/{approval_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"reviewer": "admin@example.com", "reason": "Verified defective product"}'
```

### 5. Test Guardrails

```bash
# Dollar cap exceeded (default cap: $100)
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query_text": "Refund my order ORD-12346, the total was $149.50"}'
# Expected: Blocked with "dollar_cap" reason, escalated to human review

# Invalid tool parameters
# (agent sends bad params → guardrail catches before execution)
```

## Running Tests

```bash
# Unit tests (mocked dependencies)
pytest tests/unit/ -v

# Integration tests (requires running PostgreSQL)
pytest tests/integration/ -v

# All tests
pytest -v
```

## Architecture Overview

```
Query → [existing RAG pipeline] → response_generator
                                        ↓
                                  [action_needed?]
                                   ├─ No → validate_response → END
                                   └─ Yes → action_planner → action_executor → validate_response → END
                                                                    ↓
                                                          execute_tool() ← guardrail wrapper
                                                            ├─ validate params
                                                            ├─ check rate limit
                                                            ├─ check dollar cap
                                                            ├─ check risk level
                                                            │   ├─ read-only/low → execute
                                                            │   └─ high → approval queue
                                                            └─ log audit trail
```

## Key Files

| File | Purpose |
|---|---|
| `src/tools/registry.py` | Tool definitions and discovery |
| `src/tools/guardrails.py` | Validation pipeline (params, rate limit, dollar cap, risk) |
| `src/tools/executor.py` | `execute_tool()` — the single entry point for all tool calls |
| `src/tools/approval.py` | In-memory approval queue |
| `src/tools/definitions/` | Individual tool implementations |
| `src/tools/backends/` | Simulated backend services |
| `src/agents/action_planner.py` | LLM-based tool selection node |
| `src/agents/action_executor.py` | Guardrail-wrapped execution node |

## Configuration

Environment variables / `.env` settings:

| Variable | Default | Description |
|---|---|---|
| `TOOL_RATE_LIMIT_PER_MINUTE` | 10 | Max tool calls per session per minute |
| `TOOL_DOLLAR_CAP` | 100.0 | Max dollar amount for financial actions |
| `APPROVAL_TIMEOUT_SECONDS` | 300 | Seconds before pending approvals expire |
| `TOOL_EXECUTION_ENABLED` | true | Global kill switch for tool execution |
