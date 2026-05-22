# Run Locally

End-to-end local development: FastAPI backend + Streamlit UI + Postgres/pgvector, with Langfuse traces visible at every step.

For cloud (AgentCore) deployment, see [specs/005-aws-agentcore-deployment/quickstart.md](specs/005-aws-agentcore-deployment/quickstart.md).

## Prerequisites

- Python 3.11+ (project is tested on 3.14)
- [uv](https://github.com/astral-sh/uv) for dependency management
- Docker + Docker Compose (for Postgres/pgvector)
- An OpenAI API key
- *(Optional)* Langfuse keys for observability — strongly recommended

## One-time setup

```bash
# 1. Install dependencies into a local virtualenv
uv venv && source .venv/bin/activate
uv pip install -e .

# 2. Copy the env template and fill in real values
cp .env.example .env
$EDITOR .env
```

Minimum required keys in `.env`:

```bash
OPENAI_API_KEY=sk-...                              # required
DATABASE_URL=postgresql+psycopg://agentic_rag:agentic_rag_dev@localhost:5432/agentic_rag

# Strongly recommended — without these, the Streamlit sidebar will show
# a yellow "Langfuse: disabled" badge and no traces will land.
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=https://us.cloud.langfuse.com        # or LANGFUSE_BASE_URL — both accepted
```

See [.env.example](.env.example) for the full list (tool rate limits, dollar caps, approval timeout, etc.).

## Day-to-day: three commands, three terminals

### Terminal 1 — Postgres

```bash
make up      # starts pgvector via docker compose
make seed    # ingests the knowledge base into the vector store (run once after `up`)
```

`make seed` is idempotent — safe to rerun if the schema changes. To reset everything, `make down` then `docker volume rm agentic-rag-support_pgdata`.

### Terminal 2 — FastAPI backend

```bash
.venv/bin/uvicorn src.api.main:app --reload --port 8000
```

Verify it's up and Langfuse initialized:

```bash
curl -s http://localhost:8000/health | jq
```

Expected — note the `langfuse` block:

```json
{
  "status": "healthy",
  "database": "connected",
  "vector_store": "ready",
  "llm": "configured",
  "langfuse": {
    "state": "ok",
    "source": "env",
    "host": "https://us.cloud.langfuse.com",
    "reason": ""
  }
}
```

`state` values: `"ok"` (traces will land), `"disabled"` (no credentials), `"failed"` (credentials present but init raised — check the uvicorn console for the `LANGFUSE_INIT_FAILED:` line).

### Terminal 3 — Streamlit UI

```bash
.venv/bin/streamlit run src/frontend/app.py
```

Opens at `http://localhost:8501`. The sidebar shows backend status + a Langfuse badge:

| Badge | Meaning |
|---|---|
| ✅ `Langfuse: connected (env) — <host>` | Traces will appear in the Langfuse UI |
| ⚠️ `Langfuse: disabled — <reason>` | No credentials — fix `.env` and click **Refresh status** |
| 🔴 `Langfuse: init FAILED — <reason>` | Credentials present but init crashed; check uvicorn logs |

After each query, the observability panel shows the `Langfuse trace id` — click into Langfuse to see the full span tree. If that caption is missing or shows ⚠️, the parent trace didn't open.

## Verifying Langfuse end-to-end

1. Sidebar badge is green.
2. Submit any query in the UI.
3. Observability panel shows `Langfuse trace id: <uuid>`.
4. In the [Langfuse dashboard](https://us.cloud.langfuse.com), open that trace — you should see one `agent.invoke` parent span with nested spans for the supervisor classifier, retrieval, agent LLM calls, and any tool dispatches.

If 1–3 work but no trace appears in Langfuse, your keys are wrong for the host (e.g. US keys against the EU host or vice versa).

## Make targets

```bash
make up          # docker compose up -d (Postgres)
make down        # docker compose down
make seed        # ingest knowledge base
make run         # uvicorn src.api.main:app --reload (port 8000)
make lint        # ruff check + format --check
make lint-fix    # ruff check --fix + format
make test-unit   # tests/unit/ + lambdas/
make test-int    # tests/integration/
make test-evals  # tests/evals/
make test        # all of the above
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Streamlit shows "Backend unreachable" | Start uvicorn (terminal 2). The sidebar **Retry** button re-checks. |
| Sidebar: `Langfuse: disabled — no credentials` | Set `LANGFUSE_SECRET_KEY` + `LANGFUSE_PUBLIC_KEY` in `.env`, restart uvicorn. |
| Sidebar: `Langfuse: init FAILED` | Look at the uvicorn console for `LANGFUSE_INIT_FAILED:` — usually wrong host or bad key format. |
| Observability panel says "No Langfuse trace id returned" | The parent trace didn't open; verify the sidebar badge first. If green, file a bug — the regression test in [tests/integration/test_langfuse_local_mode.py](tests/integration/test_langfuse_local_mode.py) should have caught it. |
| Empty chat responses, no citations | Ingest the knowledge base: `make seed`. |
| `psycopg.OperationalError: connection refused` | Postgres isn't up — `make up`. |
| "Streamlit not found" / module import errors | `uv pip install -e .` inside the activated `.venv`. |
| Slow responses (>30s) | OpenAI rate limit or cold cache — check API key quota. |

### Fail-fast Langfuse (CI / paranoid local)

Set `LANGFUSE_REQUIRED=true` in `.env`. Init failures (missing keys, bad rotation, network) become a hard `RuntimeError` at uvicorn startup instead of silently dropping every trace. Default is best-effort because we never want a bad rotation to take down the agent in production — but locally and in CI, fail-fast is usually what you want.
