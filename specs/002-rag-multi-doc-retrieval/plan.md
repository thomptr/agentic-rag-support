# Implementation Plan: RAG Multi-Document Retrieval

**Branch**: `002-rag-multi-doc-retrieval` | **Date**: 2026-05-09 | **Spec**: `specs/002-rag-multi-doc-retrieval/spec.md`
**Input**: Feature specification from `specs/002-rag-multi-doc-retrieval/spec.md`

## Summary

Extend the existing LangGraph supervisor agent with multi-document retrieval capabilities: cross-domain search (retrieve from multiple knowledge base domains in one query), multi-query expansion (generate search variations for better recall), and confidence-based adaptive retrieval (retry with relaxed parameters when results are weak). Use PostgreSQL pgvector (existing) for storage and RAGAS for evaluation testing that proves responses are grounded in retrieved context.

## Technical Context

| Dimension | Decision |
|---|---|
| **Language/Version** | Python 3.11+ |
| **Primary Dependencies** | `langgraph`, `langchain-anthropic`, `langchain-postgres`, `langchain-openai`, `fastapi` (all existing) |
| **New Dependencies** | `ragas` (RAG evaluation framework) |
| **LLM** | Claude via `ChatAnthropic` (existing) |
| **Embeddings** | OpenAI `text-embedding-3-small` (existing) |
| **Vector Store** | PostgreSQL 16 + pgvector (existing, user confirmed) |
| **Testing** | pytest + RAGAS (`evaluate()` with `in_ci=True`) |
| **Target Platform** | Linux server (local Docker Compose) |
| **Project Type** | Web service (FastAPI) |
| **Performance Goals** | < 30s end-to-end including retries (SC-003) |
| **Constraints** | Max 3 retrieval retries, max 20 document chunks per response |
| **Scale/Scope** | POC, 3 domains (~15 knowledge base docs), single-user |

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Research Check

| Principle | Status | Notes |
|---|---|---|
| **I. RAG-First** | PASS | This feature enhances RAG retrieval — multi-domain, multi-query, adaptive retry all increase retrieval coverage. Every response remains grounded in retrieved context. RAGAS faithfulness metric proves grounding. |
| **II. Agentic Autonomy** | PASS | Confidence-based adaptive retrieval adds autonomous decision-making: the agent independently decides when to retry retrieval and when to acknowledge knowledge gaps. |
| **III. Test-First** | PASS | TDD enforced. RAGAS evaluation suite provides quantitative proof of grounding quality. All new nodes get unit tests before implementation. |
| **IV. Observability** | PASS | FR-010 requires logging all retrieval attempts with parameters. New event types: `retrieval_plan`, `multi_retrieval`, `confidence_assessment`, `retrieval_retry`, `knowledge_gap`. |
| **V. Simplicity** | PASS | Replacing 3 nearly-identical worker agents with a unified retrieval-generation pipeline actually reduces code duplication. No new infrastructure — reuses existing pgvector and Docker Compose. RAGAS is the only new dependency. |

### Post-Design Re-Check

| Principle | Status | Notes |
|---|---|---|
| **I. RAG-First** | PASS | Unified pipeline enforces RAG-first: retrieval_planner → multi_retriever → confidence_check → response_generator. No path generates a response without retrieval. |
| **II. Agentic Autonomy** | PASS | confidence_check node autonomously decides retry vs proceed. supervisor autonomously classifies to multiple domains. |
| **III. Test-First** | PASS | RAGAS metrics (faithfulness ≥ 0.8, context_recall ≥ 0.7) provide quantitative grounding proof. Evaluation datasets cover cross-domain, single-domain, and edge cases. |
| **IV. Observability** | PASS | 5 new structured log event types capture the full retrieval lifecycle. Every retry attempt is logged with parameters and results. |
| **V. Simplicity** | PASS | One unified pipeline replaces three duplicate workers. Custom multi-query generation avoids broken LangChain `MultiQueryRetriever` (metadata filter bug). No new infrastructure. |

## Phase 0: Research Decisions

| Decision | Resolution | Rationale |
|---|---|---|
| Vector store | PostgreSQL 16 + pgvector (confirmed) | User explicitly confirmed. Already operational from 001. |
| Multi-query approach | Custom Claude-based query generation | LangChain's `MultiQueryRetriever` has metadata filter bug with PGVectorStore. Custom approach is straightforward. |
| RAG evaluation | RAGAS framework (`ragas` package) | User explicitly requested. Industry standard. Provides faithfulness, answer_relevancy, context_precision, context_recall metrics. |
| Adaptive retrieval | Similarity score + document count threshold | Simplest approach — no extra LLM call. pgvector already returns scores. |
| Graph architecture | Unified retrieval-generation pipeline | Replaces 3 duplicate domain workers. Naturally supports both single and multi-domain queries. |
| Result merging | Content-hash dedup + score-based ranking | Simple, exact, no extra dependencies. |

See `specs/002-rag-multi-doc-retrieval/research.md` for full research details.

## Phase 1: Data Model

See `specs/002-rag-multi-doc-retrieval/data-model.md` for full schema.

### State Schema Changes

New fields added to `SupportGraphState`:

| Field | Type | Purpose |
|---|---|---|
| `classified_domains` | `list[str] \| None` | Multiple domains for cross-domain queries |
| `search_queries` | `list[dict] \| None` | Generated query variations with domain targets |
| `raw_retrieval_results` | `Annotated[list[dict], _accumulate] \| None` | Unprocessed results from all queries |
| `merged_results` | `list[dict] \| None` | Deduplicated, ranked results |
| `retrieval_confidence` | `dict \| None` | Confidence assessment |
| `retrieval_attempt` | `int` | Current retry count |
| `max_retrieval_attempts` | `int` | Retry cap (default 3) |

### Database Changes

None. Existing pgvector collection and observation_logs table are sufficient.

## Phase 1: Contracts

See `specs/002-rag-multi-doc-retrieval/contracts/api.md` for full contracts.

### POST /query Response Changes

New metadata fields: `classified_domains`, `retrieval_attempts`, `documents_retrieved`, `documents_after_dedup`, `retrieval_confidence`. New citation fields: `domain`, `score`.

### Graph Node Signatures

```
supervisor(state)           → Command(goto="security_check" | "fallback_handler")
security_check(state)       → Command(goto="retrieval_planner" | "escalation_handler")
retrieval_planner(state)    → dict  (writes search_queries)
multi_retriever(state)      → dict  (writes merged_results)
confidence_check(state)     → Command(goto="retrieval_planner" | "response_generator")
response_generator(state)   → dict  (writes response_text, citations)
validate_response(state)    → dict  (existing, updated)
escalation_handler(state)   → dict  (writes response_text with escalation guidance, log_events)
```

## Project Structure

### Documentation (this feature)

```text
specs/002-rag-multi-doc-retrieval/
├── plan.md              # This file
├── research.md          # Phase 0 research decisions
├── data-model.md        # State schema extensions
├── quickstart.md        # Getting started guide
├── contracts/
│   └── api.md           # API and node contracts
└── tasks.md             # (created by /speckit-tasks)
```

### Source Code (repository root)

```text
src/
├── agents/
│   ├── supervisor.py             # MODIFIED: classify to multiple domains
│   ├── security_check.py         # NEW: policy gate (escalation + sensitive-query rules)
│   ├── retrieval_planner.py      # NEW: generate search query variations
│   ├── multi_retriever.py        # NEW: cross-domain retrieval + dedup + rank
│   ├── confidence_check.py       # NEW: evaluate retrieval quality, decide retry
│   ├── response_generator.py     # NEW: unified response generation (replaces per-domain workers)
│   ├── validate_response.py      # MODIFIED: handle multi-domain citations
│   ├── escalation_handler.py     # NEW: terminal node for security-escalated queries
│   ├── fallback.py               # UNCHANGED
│   ├── billing_agent.py          # DEPRECATED (kept for reference, removed from graph)
│   ├── technical_agent.py        # DEPRECATED
│   └── account_agent.py          # DEPRECATED (escalation logic re-homed in security_check)
│
├── graph/
│   ├── state.py                  # MODIFIED: new state fields
│   ├── workflow.py               # MODIFIED: new graph topology
│   └── routing.py                # MODIFIED: confidence-check routing logic
│
├── rag/
│   ├── retriever.py              # MODIFIED: support multi-domain and no-filter queries
│   ├── query_generator.py        # NEW: LLM-based multi-query generation
│   ├── result_merger.py          # NEW: dedup + rank + cap results
│   ├── confidence.py             # NEW: retrieval confidence scoring
│   ├── ingest.py                 # UNCHANGED
│   └── chunking.py               # UNCHANGED
│
├── observability/
│   └── logger.py                 # MODIFIED: new log event helpers
│
├── api/
│   ├── main.py                   # UNCHANGED
│   └── schemas.py                # MODIFIED: new response metadata fields
│
├── db/
│   └── connection.py             # UNCHANGED
│
└── config.py                     # MODIFIED: new config params (thresholds, retry limits)

tests/
├── unit/
│   ├── test_state.py             # MODIFIED: test new state fields
│   ├── test_retrieval_planner.py # NEW
│   ├── test_multi_retriever.py   # NEW
│   ├── test_confidence_check.py  # NEW
│   ├── test_response_generator.py # NEW
│   ├── test_query_generator.py   # NEW
│   ├── test_result_merger.py     # NEW
│   ├── test_confidence.py        # NEW
│   ├── test_routing.py           # MODIFIED
│   ├── test_supervisor.py        # MODIFIED
│   └── test_logger.py            # MODIFIED
│
├── integration/
│   ├── test_retriever.py         # MODIFIED: test multi-domain queries
│   ├── test_workflow.py          # MODIFIED: test new graph topology
│   └── test_api.py               # MODIFIED: test new response fields
│
└── evals/
    ├── test_rag_quality.py       # NEW: RAGAS evaluation suite
    ├── test_routing_accuracy.py  # MODIFIED: test multi-domain classification
    └── datasets/
        ├── cross_domain.json     # NEW: cross-domain test cases
        ├── single_domain.json    # NEW: regression test cases
        └── edge_cases.json       # NEW: adaptive retrieval test cases
```

**Structure Decision**: Extends the existing single-project structure from 001. New modules are added under `src/rag/` (retrieval logic) and `src/agents/` (graph nodes). No new top-level directories.

## LangGraph Flow

```
START → supervisor → [conditional] → security_check → [conditional] → retrieval_planner → multi_retriever → confidence_check → [conditional] → response_generator → validate_response → END
                   → fallback_handler → END         → escalation_handler → END                  ↑                                            → retrieval_planner (retry)
                                                                                                 └─────────────────────────────────────────────┘
```

A canonical visual rendering lives at [`docs/architecture/langgraph.mmd`](../../docs/architecture/langgraph.mmd).

### Node Descriptions

- **supervisor**: Calls the LLM with structured output to classify the query into 1+ domains. Returns `Command(goto="security_check")` for classifiable queries, `Command(goto="fallback_handler")` for unknown.
- **security_check**: Policy gate that runs *before* retrieval. Combines fast rule-based checks (keyword/regex deny-lists, sensitive-pattern detection — e.g. account-takeover phrasing, fraud signals) with optional LLM-assisted classification when needed. Returns `Command(goto="escalation_handler")` for queries that must bypass retrieval (active security incidents, takeover reports), or `Command(goto="retrieval_planner")` for safe queries. Emits `security_signals` on state for downstream consumers (audit trail, response_generator hardening).
- **retrieval_planner**: Uses the LLM to generate 2-3 search query variations from the original question, each targeting a specific domain. For simple single-domain queries, may generate just 1 query.
- **multi_retriever**: Executes all search queries against pgvector (with domain filters), collects results, deduplicates by content hash, ranks by similarity score, caps at 20 documents.
- **confidence_check**: Evaluates retrieval quality (avg similarity, result count). Routes to `retrieval_planner` for retry (with broadened params) or `response_generator` to proceed.
- **response_generator**: Prompts the LLM with retrieved documents to generate a grounded response with per-document citations including domain attribution.
- **validate_response**: Checks that response contains citations, logs final metrics.
- **fallback_handler**: Returns acknowledgement without retrieval (unchanged from 001).
- **escalation_handler**: Terminal node for security-escalated queries. Emits a high-priority response routing the user to the security/incident-response team without burning RAG tokens, and logs an `escalation_triggered` event with the originating policy signals.

## RAGAS Evaluation Strategy

### Metrics and Thresholds

| Metric | Threshold | What It Proves |
|---|---|---|
| Faithfulness | ≥ 0.8 | Responses are grounded — every claim traces to retrieved docs |
| Answer Relevancy | ≥ 0.65 | Responses actually address the user's question (threshold accounts for LLM-judge variance on small datasets) |
| Context Precision | ≥ 0.65 | Retrieved documents are relevant and well-ranked (LLM-judge variance tolerance) |
| Context Recall | ≥ 0.65 | Retrieval finds all necessary documents (LLM-judge variance tolerance) |

### Evaluation Datasets

| Dataset | Cases | Purpose |
|---|---|---|
| `cross_domain.json` | 5-8 | Queries spanning 2-3 domains with known ground-truth |
| `single_domain.json` | 5-8 | Single-domain queries for regression testing |
| `edge_cases.json` | 3-5 | Sparse coverage, contradictory info, context overflow |

### Integration with pytest

```python
@pytest.mark.ragas_ci
def test_cross_domain_faithfulness():
    results = evaluate(dataset, metrics=[faithfulness], llm=llm, in_ci=True)
    assert results["faithfulness"] >= 0.8
```

## Dependencies (pyproject.toml changes)

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "httpx>=0.27",
    "pytest-cov>=6.0",
    "ragas>=0.2",
]
```

## Configuration Changes

New settings in `config.py`:

| Setting | Default | Description |
|---|---|---|
| `CONFIDENCE_THRESHOLD` | 0.6 | Minimum average similarity for confident retrieval |
| `MIN_RESULT_COUNT` | 3 | Minimum documents required for confident retrieval |
| `MAX_RETRIEVAL_ATTEMPTS` | 3 | Maximum retry attempts before acknowledging gap |
| `MAX_CONTEXT_DOCUMENTS` | 20 | Maximum documents passed to response generator |
| `MULTI_QUERY_COUNT` | 3 | Number of search query variations to generate |

## Implementation Sequence (TDD)

Each step: write test (RED) → confirm fail → implement (GREEN).

### Phase 1: State & Config

1. Extend state schema with new fields → `test_state.py`
2. Add new config parameters → implicit test via settings load
3. Add new observability log helpers → `test_logger.py`

### Phase 2: RAG Pipeline Components

4. Implement query generator → `test_query_generator.py` → `rag/query_generator.py`
5. Implement result merger → `test_result_merger.py` → `rag/result_merger.py`
6. Implement confidence scorer → `test_confidence.py` → `rag/confidence.py`
7. Extend retriever for multi-domain → `test_retriever.py` → `rag/retriever.py`

### Phase 3: Graph Nodes (User Story 1 — Cross-Domain)

8. Modify supervisor for multi-domain classification → `test_supervisor.py`
9. Implement retrieval_planner node → `test_retrieval_planner.py`
10. Implement multi_retriever node → `test_multi_retriever.py`
11. Implement response_generator node → `test_response_generator.py`

### Phase 4: Adaptive Retrieval (User Story 3)

12. Implement confidence_check node → `test_confidence_check.py`
13. Update routing for retry loop → `test_routing.py`

### Phase 5: Graph Assembly

14. Build new graph topology → `test_workflow.py`
15. Update validate_response → existing tests
16. Update API schemas → `test_api.py`

### Phase 6: RAGAS Evaluation (User Story 2 verification + grounding proof)

17. Create evaluation datasets → `tests/evals/datasets/`
18. Implement RAGAS test suite → `test_rag_quality.py`
19. Update routing accuracy evals → `test_routing_accuracy.py`

### Phase 7: Security Layer (User Story 4 — Sensitive Query Handling)

20. Implement security_check rules + tests → `test_security_check.py` → `agents/security_check.py`
21. Implement escalation_handler node + tests → `test_escalation_handler.py` → `agents/escalation_handler.py`
22. Wire security_check into graph topology between supervisor and retrieval_planner → `test_workflow.py` (new test cases)
23. Restore the `test_account_agent_triggers_escalation_for_takeover` end-to-end assertion against the new path → `tests/evals/test_end_to_end.py`

### Architecture Rationale: Why a Dedicated Policy Node

Three placements were considered for sensitive-query handling (account takeover, fraud signals, future PII / plan-tier policies):

| Option | Where | Trade-off |
|---|---|---|
| **A. Dedicated `security_check` node** *(chosen)* | After supervisor, before retrieval_planner | Single responsibility, can short-circuit retrieval entirely, mixes LLM and rule-based checks freely, composes with future domain workers. Cost: one extra hop on every request (a fast keyword pre-check is sub-millisecond). |
| B. Fold into supervisor's structured output | Supervisor schema gains `sensitivity_flags` | Cheapest plumbing, but bloats supervisor's responsibility, couples *where to route* with *what policy applies*, harder to add non-LLM checks. |
| C. Inside response_generator | Post-retrieval policy check | Wrong tradeoff for security: pays embedding + retrieval + generation costs before deciding to escalate. Bad latency for active incidents. |

Option A is the cleanest long-term pattern: security_check produces *signals* on state, escalation_handler enforces, and future policy concerns (PII redaction, plan-tier gating, prompt-injection guards) can be layered into the same node without touching unrelated agents.

## Conflict Resolutions

| Conflict | Resolution |
|---|---|
| Constitution tech stack says "lightweight store preferred (ChromaDB/FAISS)" | pgvector already chosen and operational in 001. User explicitly confirmed pgvector for 002. Constitution's "TBD during Phase 0" language anticipated this. |
| Existing per-domain workers vs unified pipeline | Unified pipeline is simpler (Principle V) — eliminates 3 nearly-identical functions. Per-domain workers are deprecated, not deleted, for reference. |
| RAGAS requires LLM for metric computation | Uses the existing Claude configuration. Cost is acceptable for POC evaluation testing. |

## Verification

1. `make test-unit` — All unit tests pass (mocked dependencies)
2. `make test-int` — Integration tests pass (real Postgres)
3. `make test-evals` — RAGAS evaluation suite passes all thresholds
4. Cross-domain query returns citations from multiple domains
5. Adaptive retrieval retries on low-confidence results
6. Knowledge gap acknowledged when retrieval remains insufficient
7. Single-domain queries perform within 10% of 001 baseline (SC-005)
8. All retrieval attempts logged with full parameters (SC-006)
