# Implementation Plan: Frontend Chat UI, Agent Observability & Demo Console

**Branch**: `004-frontend-chat-observability` | **Date**: 2026-05-09 | **Spec**: `specs/004-frontend-chat-observability/spec.md`
**Input**: Feature specification from `specs/004-frontend-chat-observability/spec.md`

## Summary

Build a Streamlit-based frontend that provides a chat interface for submitting support queries, an observability panel for inspecting agent execution traces (routing, RAG sources, tool calls, guardrail events), and a demo console with preset scenarios and controls. The UI consumes the existing FastAPI `/query` and `/approvals` endpoints — no new backend logic required. Layout follows `design/streamlit-layout.md`: left sidebar for controls (customer, scenario, guardrails, model, reset), main area for chat + final answer, and right expandable tabs for agent route, RAG sources, tool calls, guardrail events, and raw state JSON.

## Technical Context

| Dimension | Decision |
|---|---|
| **Language/Version** | Python 3.11+ |
| **Primary Dependencies** | `streamlit` (new), `httpx` (existing test dependency, now also used in frontend) |
| **Existing Dependencies** | `fastapi`, `langgraph`, `langchain-openai`, `langchain-postgres`, `structlog` (all unchanged) |
| **LLM** | Claude via `ChatAnthropic` / OpenAI via `ChatOpenAI` (existing, unchanged) |
| **Storage** | None new — conversation state held in Streamlit session state (in-memory, single session) |
| **Testing** | pytest for backend integration tests; manual browser testing for UI |
| **Target Platform** | Desktop browser (Chrome/Firefox), served via `streamlit run` |
| **Project Type** | Web application (Streamlit frontend + existing FastAPI backend) |
| **Performance Goals** | < 30s for typical query round-trip (SC-001); UI renders within 1s of response |
| **Constraints** | Single-session (no persistence across refreshes); desktop only; no auth |
| **Scale/Scope** | POC demo, 9+ preset scenarios, single concurrent user |

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Research Check

| Principle | Status | Notes |
|---|---|---|
| **I. RAG-First** | PASS | Frontend only displays results from the existing RAG pipeline. Does not bypass or modify retrieval. The UI renders retrieved documents with relevance scores, reinforcing RAG transparency. |
| **II. Agentic Autonomy** | PASS | No change to agent decision-making. Frontend consumes agent outputs and displays them. The guardrails toggle controls the existing backend `tool_execution_enabled` config — agents still decide autonomously. |
| **III. Test-First** | PASS | Backend integration tests verify API contract from the frontend's perspective. UI components tested via manual browser testing (standard for Streamlit POC — no Streamlit unit test framework required for a demo tool). |
| **IV. Observability** | PASS | Core enabler. The observability panel makes existing structured log data and response metadata visible to humans. This feature directly serves Principle IV by surfacing agent decision traces. |
| **V. Simplicity** | PASS | Streamlit is the simplest viable framework — single Python file, no build step, no JS toolchain. Layout follows a single-page design. No custom components, no WebSocket streaming, no persistent state. |

### Post-Design Re-Check

| Principle | Status | Notes |
|---|---|---|
| **I. RAG-First** | PASS | RAG Sources tab prominently displays retrieved documents with content, domain, source, and relevance scores. Citations are rendered inline with responses. |
| **II. Agentic Autonomy** | PASS | Agent Route tab shows supervisor routing decisions and confidence rationale. Users observe but do not override agent decisions. |
| **III. Test-First** | PASS | Integration tests validate `/query` and `/approvals` endpoints return expected schema. UI behavior verified through manual testing with preset scenarios (SC-004: full demo walkthrough in <2 min). |
| **IV. Observability** | PASS | Five dedicated tabs expose full execution trace: agent route, RAG sources, tool calls, guardrail events, and raw state JSON. Every queryable metric from the backend is surfaced. |
| **V. Simplicity** | PASS | Single `app.py` Streamlit entry point with three component modules. No component libraries, no state management frameworks, no build pipeline. `httpx` for API calls. Sidebar controls use native Streamlit widgets. |

## Phase 0: Research Decisions

| Decision | Resolution | Rationale |
|---|---|---|
| Frontend framework | Streamlit | User specified Streamlit in the design doc. Simplest Python-only option — no JS build step, no separate frontend project. Fits POC scope (Principle V). |
| HTTP client | `httpx` | Already a project dependency (used in tests). Supports sync calls which align with Streamlit's execution model. |
| Chat UI pattern | `st.chat_message` + `st.chat_input` | Streamlit's native chat components. No custom HTML needed. Handles message bubbles, avatars, and input natively. |
| Observability data source | `/query` response metadata + citations + tool_calls | All trace data needed is already in the `QueryResponse` schema. No need to parse structlog output or add new endpoints. |
| Guardrails toggle | Sidebar toggle that sends override with each request | Frontend sends a flag with each request. Backend already has `tool_execution_enabled` config — extend `/query` to accept an override parameter. |
| Model selection | Sidebar selectbox | Frontend sends model preference as a parameter. Backend config already supports `llm_model`. Extend `/query` to accept a model override. |
| Customer selection | Sidebar selectbox with preset customer IDs | Maps to `session_id` in the query request. Different customers provide different demo contexts. |
| Layout structure | Sidebar + main area + expander tabs | Follows `design/streamlit-layout.md`. Sidebar for controls, main for chat, `st.expander` or `st.tabs` for observability. |
| Streaming responses | Not implemented (v1) | Streamlit does not natively support streaming from external HTTP APIs without SSE/WebSocket backend support. Out of scope for POC — full response rendered on completion. |
| Session persistence | Streamlit `st.session_state` only | No database, no cookies. Conversation resets on browser refresh. Meets spec assumption: "single-session mode." |

See `specs/004-frontend-chat-observability/research.md` for full research details.

## Phase 1: Data Model

See `specs/004-frontend-chat-observability/data-model.md` for full schema.

### Frontend State (Streamlit session_state)

| Key | Type | Purpose |
|---|---|---|
| `messages` | `list[dict]` | Conversation history: `{"role": "user"\|"assistant", "content": str, "trace": dict\|None}` |
| `selected_customer` | `str` | Currently selected customer ID for session context |
| `selected_scenario` | `str\|None` | Currently selected preset scenario (or None for freeform) |
| `guardrails_enabled` | `bool` | Whether tool guardrails are active |
| `selected_model` | `str` | LLM model to use for queries |
| `pending_approvals` | `list[dict]` | Approval items awaiting action |
| `last_trace` | `dict\|None` | Full trace data from the most recent query response |

### Backend Changes

| Change | Scope | Purpose |
|---|---|---|
| Add `guardrails_enabled` to `QueryRequest` | `src/api/schemas.py` | Allow frontend to toggle tool execution per-request |
| Add `model_override` to `QueryRequest` | `src/api/schemas.py` | Allow frontend to select model per-request |
| Pass overrides through to graph invocation | `src/api/main.py` | Wire request params to graph config |

### Key Entities (Frontend)

| Entity | Fields | Purpose |
|---|---|---|
| **ChatMessage** | role, content, timestamp, trace | A single message in the conversation with optional trace data |
| **TraceData** | agent, routing_rationale, metadata, citations, tool_calls, pending_approvals, raw_response | Full observability payload attached to assistant messages |
| **PresetScenario** | id, category, title, query_text, description | A predefined demo query with category grouping |
| **CustomerProfile** | id, name, description | A selectable customer identity for demo context |

### No Database Changes

All frontend state is held in Streamlit session state. No new tables, no persistence layer.

## Phase 1: Contracts

See `specs/004-frontend-chat-observability/contracts/api.md` for full contracts.

### Modified API Endpoints

| Method | Path | Change |
|---|---|---|
| POST | `/query` | Accept optional `guardrails_enabled` and `model_override` fields in request body |

### Existing Endpoints Consumed (unchanged)

| Method | Path | Frontend Usage |
|---|---|---|
| POST | `/query` | Submit chat messages, receive responses + trace data |
| GET | `/approvals` | Poll for pending approval items |
| POST | `/approvals/{id}/approve` | Approve a pending tool action |
| POST | `/approvals/{id}/reject` | Reject a pending tool action |
| GET | `/health` | Validate backend connectivity on startup |

### Frontend to Backend Data Flow

```
User types message
  -> Streamlit captures via st.chat_input
  -> POST /query { query_text, session_id, guardrails_enabled, model_override }
  -> Backend processes through LangGraph
  -> Returns QueryResponse { response_text, agent, routing_rationale, citations, metadata, tool_calls, pending_approvals }
  -> Streamlit renders response in chat + populates observability tabs
```

## Project Structure

### Documentation (this feature)

```text
specs/004-frontend-chat-observability/
├── plan.md              # This file
├── research.md          # Phase 0 research decisions
├── data-model.md        # Frontend state + entity definitions
├── quickstart.md        # Getting started guide
├── contracts/
│   └── api.md           # API contract modifications
└── tasks.md             # (created by /speckit-tasks)
```

### Source Code (repository root)

```text
src/
├── frontend/
│   ├── app.py                   # NEW: Main Streamlit application
│   ├── api_client.py            # NEW: httpx wrapper for backend calls
│   ├── components/
│   │   ├── sidebar.py           # NEW: Left sidebar controls
│   │   ├── chat.py              # NEW: Chat message rendering
│   │   └── observability.py     # NEW: Right-side trace tabs
│   └── scenarios.py             # NEW: Preset scenario definitions
│
├── api/
│   ├── main.py                  # MODIFIED: wire guardrails_enabled + model_override from request
│   └── schemas.py               # MODIFIED: add optional fields to QueryRequest
│
├── agents/                      # UNCHANGED
├── tools/                       # UNCHANGED
├── graph/                       # UNCHANGED
├── rag/                         # UNCHANGED
├── observability/               # UNCHANGED
├── db/                          # UNCHANGED
└── config.py                    # UNCHANGED

tests/
├── unit/
│   ├── test_api_client.py       # NEW: API client wrapper tests
│   ├── test_scenarios.py        # NEW: preset scenario data validation
│   └── ...                      # EXISTING tests unchanged
│
├── integration/
│   ├── test_query_overrides.py  # NEW: guardrails_enabled + model_override through API
│   └── ...                      # EXISTING tests unchanged
│
└── evals/
    └── ...                      # EXISTING evals unchanged
```

**Structure Decision**: New `src/frontend/` module for all Streamlit code. Components split by UI region (sidebar, chat, observability) for readability. Backend changes minimal — only `schemas.py` and `main.py` touched to accept new optional request fields.

## UI Layout

```
+------------------------------------------------------------------------------+
| Agentic RAG Support Demo                                                     |
+--------------+-------------------------------+-------------------------------+
|  SIDEBAR     |  MAIN AREA                    |  OBSERVABILITY (expandable)   |
|              |                               |                               |
|  Customer:   |  [Chat messages]              |  > Agent Route                |
|  [dropdown]  |                               |    - Classified domain(s)     |
|              |  User: How do I update        |    - Routed to agent          |
|  Scenario:   |     my billing info?          |    - Routing rationale        |
|  [dropdown]  |                               |    - Confidence               |
|              |  Assistant: You can           |                               |
|  Guardrails: |     update your billing...    |  > RAG Sources                |
|  [toggle]    |                               |    - Document 1 (score: 0.87) |
|              |  ---                          |    - Document 2 (score: 0.82) |
|  Model:      |                               |                               |
|  [dropdown]  |  [Final answer summary]       |  > Tool Calls                 |
|              |                               |    - order_status: success    |
|  [Reset      |                               |                               |
|   Convo]     |  +---------------------+      |  > Guardrail Events           |
|              |  | Type a message...   |      |    - Rate limit: OK           |
|              |  +---------------------+      |    - Dollar cap: OK           |
|              |                               |                               |
|              |                               |  > Raw State JSON             |
|              |                               |    { full response object }    |
+--------------+-------------------------------+-------------------------------+
```

## Preset Scenarios

| Category | Title | Query |
|---|---|---|
| **Billing** | Update billing info | "How do I update my billing information?" |
| **Billing** | Invoice dispute | "I was charged twice on my last invoice. Can you help?" |
| **Billing** | Payment methods | "What payment methods do you accept?" |
| **Technical** | API rate limits | "What are the API rate limits for the pro plan?" |
| **Technical** | Integration setup | "How do I set up the webhook integration?" |
| **Technical** | Error troubleshooting | "I'm getting a 502 error when calling the API." |
| **Account** | Reset password | "How do I reset my password?" |
| **Account** | Account permissions | "How do I add a new team member to my account?" |
| **Account** | Cancel subscription | "I want to cancel my subscription." |

Minimum 9 scenarios (3 per category) to meet SC-003.

## Customer Profiles

| ID | Name | Description |
|---|---|---|
| `cust-001` | Acme Corp | Enterprise customer, billing-heavy |
| `cust-002` | Startup Inc | Small team, technical questions |
| `cust-003` | Demo User | Generic demo identity |

## Configuration Changes

### Backend (minimal)

New optional fields in `QueryRequest`:

| Field | Type | Default | Description |
|---|---|---|---|
| `guardrails_enabled` | `bool \| None` | `None` (use server default) | Override tool_execution_enabled per-request |
| `model_override` | `str \| None` | `None` (use server default) | Override llm_model per-request |

### Frontend (new)

| Setting | Default | Description |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8000` | FastAPI backend base URL |
| `REQUEST_TIMEOUT` | `30` | Seconds before request timeout |

## Implementation Sequence (TDD)

Each step: write test (RED) -> confirm fail -> implement (GREEN).

### Phase 1: Backend Contract Extensions

1. Add `guardrails_enabled` and `model_override` to `QueryRequest` schema -> `test_query_overrides.py` -> `schemas.py`
2. Wire overrides through `/query` endpoint to graph invocation -> `test_query_overrides.py` -> `main.py`

### Phase 2: Frontend API Client

3. Implement `api_client.py` with `send_query()`, `get_approvals()`, `approve()`, `reject()`, `health_check()` -> `test_api_client.py` -> `frontend/api_client.py`

### Phase 3: Preset Scenarios & Data

4. Define preset scenarios data structure -> `test_scenarios.py` -> `frontend/scenarios.py`
5. Define customer profiles -> `frontend/scenarios.py`

### Phase 4: Streamlit UI -- Sidebar (User Story 3)

6. Implement sidebar with customer selector, scenario selector, guardrails toggle, model selector, reset button -> `frontend/components/sidebar.py`

### Phase 5: Streamlit UI -- Chat (User Story 1)

7. Implement chat message display with `st.chat_message` -> `frontend/components/chat.py`
8. Implement message input and submission flow -> `frontend/app.py`
9. Implement loading indicator during query processing -> `frontend/app.py`
10. Implement welcome state with example prompts -> `frontend/app.py`
11. Implement error handling for backend failures -> `frontend/app.py`

### Phase 6: Streamlit UI -- Observability (User Story 2)

12. Implement Agent Route tab (domain classification, routing, rationale) -> `frontend/components/observability.py`
13. Implement RAG Sources tab (retrieved documents with scores) -> `frontend/components/observability.py`
14. Implement Tool Calls tab (execution results, statuses) -> `frontend/components/observability.py`
15. Implement Guardrail Events tab (rate limits, dollar caps, approvals) -> `frontend/components/observability.py`
16. Implement Raw State JSON tab -> `frontend/components/observability.py`

### Phase 7: Integration & Polish

17. Wire sidebar controls to query parameters -> `frontend/app.py`
18. Implement approval management in sidebar or inline -> `frontend/app.py`
19. End-to-end manual testing with all preset scenarios
20. Verify SC-004: full demo walkthrough in < 2 minutes

## Conflict Resolutions

| Conflict | Resolution |
|---|---|
| Streamlit reruns entire script on interaction | Use `st.session_state` to persist conversation history and UI state across reruns. All stateful data stored in session state, not module-level variables. |
| Spec mentions "real-time streaming" | Deferred. Streamlit does not natively support streaming from external HTTP APIs without SSE/WebSocket backend support. V1 renders complete responses. Loading indicator provides feedback during processing. |
| Observability panel layout (right side vs tabs) | Use `st.columns` for side-by-side layout on wide screens with `st.expander` inside the right column. Falls back cleanly to full-width on narrower screens. |
| Backend guardrails toggle requires per-request control | Add optional `guardrails_enabled` field to `QueryRequest`. When `None`, backend uses its default config. When set, overrides for that request only. |

## Verification

1. `make test-unit` -- All existing unit tests pass (no regressions)
2. `make test-int` -- Integration tests pass including new query override tests
3. Chat UI: user can type a question and receive a response (SC-001: < 30s)
4. Observability: every response has trace data in all 5 tabs (SC-002)
5. Demo console: 9+ preset scenarios across 3 categories (SC-003)
6. Demo walkthrough: query -> response -> trace inspection in < 2 minutes (SC-004)
7. Error states: backend unreachable shows friendly message within 5s (SC-005)
8. Sidebar controls: customer, scenario, guardrails, model, and reset all functional
9. Approval management: pending approvals visible and actionable from the UI
10. Existing backend tests continue to pass (no regressions)
