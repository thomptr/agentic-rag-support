# Quickstart: Frontend Chat UI, Agent Observability & Demo Console

**Feature**: `004-frontend-chat-observability`

## Prerequisites

- Python 3.11+
- Docker and Docker Compose (for PostgreSQL + pgvector)
- `.env` file configured (see `.env.example`)
- Knowledge base ingested (see Feature 001 docs)

## Setup

### 1. Install dependencies

```bash
uv sync
```

This installs `streamlit` and `httpx` alongside existing project dependencies.

### 2. Start the database

```bash
docker compose up -d
```

### 3. Start the backend

```bash
uvicorn src.api.main:app --reload --port 8000
```

Verify the backend is healthy:

```bash
curl http://localhost:8000/health
```

### 4. Start the frontend

In a separate terminal:

```bash
streamlit run src/frontend/app.py
```

The app opens in your browser at `http://localhost:8501`.

## Using the Demo

### Chat Interface

1. Type a support question in the text input at the bottom
2. Press Enter or click Send
3. The agent's response appears in the chat area
4. Trace data populates in the right panel

### Sidebar Controls

- **Customer**: Select a customer profile to set the session context
- **Scenario**: Choose a preset scenario to auto-fill the chat input
- **Guardrails**: Toggle tool execution guardrails on/off
- **Model**: Select the LLM model for processing
- **Reset Conversation**: Clear all messages and start fresh

### Observability Panel

After each response, inspect the five tabs:

- **Agent Route**: Which domain was classified, which agent handled it, and why
- **RAG Sources**: Retrieved documents with relevance scores
- **Tool Calls**: Any tools that were executed, blocked, or pending approval
- **Guardrail Events**: Rate limit, dollar cap, and risk-level check results
- **Raw State JSON**: Full backend response for debugging

### Approval Workflow

When a high-risk tool (e.g., `issue_refund`) is triggered:

1. The response shows a "Pending Approval" notice
2. Review the tool name, parameters, and risk level
3. Click Approve or Reject
4. The tool executes (or is rejected) and the result is displayed

## Running Tests

```bash
# Unit tests
make test-unit

# Integration tests (requires running backend)
make test-int

# All tests
make test
```

## Troubleshooting

| Issue | Solution |
|---|---|
| "Connection refused" error in UI | Ensure the FastAPI backend is running on port 8000 |
| Empty chat responses | Check that the knowledge base is ingested and the database is running |
| Streamlit not found | Run `uv sync` to install dependencies |
| Slow responses (> 30s) | Check LLM API connectivity and rate limits |
