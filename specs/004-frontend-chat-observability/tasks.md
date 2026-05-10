# Tasks: Frontend Chat UI, Agent Observability & Demo Console

**Input**: Design documents from `specs/004-frontend-chat-observability/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md
**Context**: Connect Streamlit frontend to local LangGraph workflow via existing FastAPI `/query` and `/approvals` endpoints

**Tests**: Included for backend contract changes and shared data modules (TDD per plan.md). UI components tested via manual browser testing per spec.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create frontend module structure and install dependencies

- [X] T001 Create frontend directory structure: `src/frontend/__init__.py`, `src/frontend/components/__init__.py` per plan.md project structure
- [X] T002 Add `streamlit` dependency to `pyproject.toml` (`httpx` already present as test dependency)

---

## Phase 2: Foundational (Backend Contract Extensions + API Client)

**Purpose**: Extend the `/query` endpoint to accept per-request overrides and build the shared HTTP client that connects the Streamlit frontend to the local LangGraph workflow

**CRITICAL**: No user story work can begin until this phase is complete -- the API client is the bridge between the frontend and the LangGraph supervisor graph

### Backend Schema & Wiring

- [X] T003 Add optional `guardrails_enabled: bool | None = None` and `model_override: str | None = None` fields to `QueryRequest` in `src/api/schemas.py`
- [X] T004 Wire `guardrails_enabled` and `model_override` from request through `/query` endpoint to graph invocation config, with model whitelist validation (`gpt-4o-mini`, `gpt-4o`, `claude-sonnet-4-6`) in `src/api/main.py`

### Tests & API Client

- [X] T005 [P] Write integration tests verifying `guardrails_enabled` and `model_override` are accepted and passed through to graph config in `tests/integration/test_query_overrides.py`
- [X] T006 [P] Write unit tests for API client functions (`send_query`, `get_approvals`, `approve_action`, `reject_action`, `health_check`) in `tests/unit/test_api_client.py`
- [X] T007 Implement API client using httpx sync with `BACKEND_URL` (`http://localhost:8000`) and `REQUEST_TIMEOUT` (30s) config -- methods: `send_query()`, `get_approvals()`, `approve_action()`, `reject_action()`, `health_check()` in `src/frontend/api_client.py`

**Checkpoint**: Backend accepts override parameters. API client can connect to local LangGraph workflow via FastAPI. All user stories can now proceed.

---

## Phase 3: User Story 1 -- Chat with Support Agent (Priority: P1) MVP

**Goal**: Users can type support questions in a browser-based chat interface and receive agent responses routed through the LangGraph supervisor workflow

**Independent Test**: Open the app at `http://localhost:8501`, type "How do I update my billing info?", verify a relevant response appears in the chat within 30 seconds (SC-001)

### Implementation for User Story 1

- [X] T008 [P] [US1] Implement chat message display component using `st.chat_message` for user/assistant message bubbles with role-based avatars in `src/frontend/components/chat.py`
- [X] T009 [US1] Implement main Streamlit app entry point: page config, session state initialization (`messages`, `session_id`, `last_trace`, `pending_approvals`, `guardrails_enabled`, `selected_model`), chat history rendering via chat component, and `st.chat_input` submission flow calling `api_client.send_query()` in `src/frontend/app.py`
- [X] T010 [US1] Add `st.spinner` loading indicator during query processing and welcome state with app title, description, and example prompt buttons when `messages` is empty in `src/frontend/app.py`
- [X] T011 [US1] Add error handling: catch `httpx.ConnectError` (backend unreachable, SC-005), `httpx.TimeoutException` (slow responses), `httpx.HTTPStatusError` (API errors) -- display user-friendly `st.error` messages with retry guidance in `src/frontend/app.py`

**Checkpoint**: User Story 1 fully functional -- users can chat with the LangGraph-powered support agent through the browser. Delivers a complete end-to-end demo experience.

---

## Phase 4: User Story 2 -- View Agent Trace & Observability Panel (Priority: P2)

**Goal**: After each response, users can inspect the full agent execution trace: supervisor routing, RAG retrieval sources, tool calls, guardrail events, and raw state JSON

**Independent Test**: Send a query, inspect the observability panel -- verify all five tabs display correct trace data from the `QueryResponse` (SC-002: 100% of responses have viewable traces)

### Implementation for User Story 2

- [X] T012 [US2] Implement observability component with five `st.tabs`: (1) Agent Route -- classified domain(s), routed agent, routing rationale, confidence via `st.expander`; (2) RAG Sources -- one `st.expander` per citation with content, domain, source, relevance score bar; (3) Tool Calls -- one `st.expander` per tool call with tool_name, status badge, result, error; (4) Guardrail Events -- blocked tool calls (block_reason), pending approvals with parameters; (5) Raw State JSON -- `st.json()` of full response. Include empty state when no traces available in `src/frontend/components/observability.py`
- [X] T013 [US2] Add query metrics summary row (`st.metric` widgets for total_latency_ms, llm_calls, retrieval_calls, documents_retrieved, retrieval_confidence) above observability tabs in `src/frontend/components/observability.py`
- [X] T014 [US2] Update main app layout to three-column design using `st.columns([2, 1])` -- render chat in left column, wire `last_trace` from session state to observability component in right column in `src/frontend/app.py`

**Checkpoint**: User Stories 1 AND 2 work together. Every chat response shows full trace data across five observability tabs with timing metrics.

---

## Phase 5: User Story 3 -- Demo Console with Preset Scenarios (Priority: P3)

**Goal**: Demo operators can select preset scenarios and customer profiles from a sidebar to quickly showcase the system without typing custom queries

**Independent Test**: Select a preset scenario from the sidebar, verify the query populates in chat and produces a response with full observability trace (SC-003: 9+ scenarios across 3 categories, SC-004: full demo walkthrough in < 2 min)

### Tests for User Story 3

- [X] T015 [P] [US3] Write unit tests validating preset scenario data structure (9+ scenarios, 3+ per category, all fields present) and customer profile completeness in `tests/unit/test_scenarios.py`

### Implementation for User Story 3

- [X] T016 [P] [US3] Define 9 preset scenarios (3 billing: update billing, invoice dispute, payment methods; 3 technical: API rate limits, webhook integration, error troubleshooting; 3 account: reset password, account permissions, cancel subscription) and 3 customer profiles (`cust-001` Acme Corp, `cust-002` Startup Inc, `cust-003` Demo User) in `src/frontend/scenarios.py`
- [X] T017 [US3] Implement sidebar component using `st.sidebar` with `st.selectbox` for customer, `st.selectbox` for scenario (grouped by category), `st.toggle` for guardrails (default: on), `st.selectbox` for model (`gpt-4o-mini`, `gpt-4o`, `claude-sonnet-4-6`), and `st.button` for reset conversation in `src/frontend/components/sidebar.py`
- [X] T018 [US3] Wire sidebar into main app: render sidebar component, scenario selection auto-fills and submits query, customer maps to `session_id`, guardrails/model pass to `send_query()`, reset clears `messages`/`last_trace`/`pending_approvals` in `src/frontend/app.py`

**Checkpoint**: All three user stories independently functional. Full demo console with 9 preset scenarios, sidebar controls, and observability.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Approval workflow, end-to-end validation, and final polish

- [X] T019 Implement approval management UI: display `pending_approvals` count in sidebar, expandable approval cards showing tool_name/parameters/risk, Approve/Reject buttons calling `api_client.approve_action()` / `reject_action()` in `src/frontend/app.py`
- [X] T020 End-to-end manual testing: run all 9 preset scenarios across 3 customer profiles, verify chat responses (SC-001), trace data in all 5 tabs (SC-002), sidebar controls functional, error states display friendly messages (SC-005), and approval workflow works
- [X] T021 Validate `specs/004-frontend-chat-observability/quickstart.md` instructions: fresh `uv sync`, start backend, start frontend, complete full demo walkthrough in < 2 minutes (SC-004)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies -- can start immediately
- **Foundational (Phase 2)**: Depends on Setup -- BLOCKS all user stories
- **US1 Chat (Phase 3)**: Depends on Foundational (API client must exist to connect to LangGraph)
- **US2 Observability (Phase 4)**: Depends on US1 (observability panel renders trace data from chat responses)
- **US3 Demo Console (Phase 5)**: Scenarios data (T015, T016) can start after Foundational; sidebar wiring (T017, T018) needs app structure from US1
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Phase 2 -- no dependencies on other stories
- **User Story 2 (P2)**: Depends on US1 -- trace data comes from chat responses rendered in the main app
- **User Story 3 (P3)**: Scenarios data is independent; sidebar wiring integrates with US1 app structure

### Within Each User Story

- Tests written first, confirmed to fail before implementation (TDD)
- API client / data modules before UI components
- Components before wiring into main app
- Commit after each task or logical group

### Parallel Opportunities

- T005 and T006 can run in parallel (different test files, independent)
- T008 (chat component) can start while T007 (API client) completes (different files)
- T015 and T016 can run in parallel (test file vs implementation file)
- US3 scenario data (T015, T016) can begin as soon as Foundational completes, even while US1 is in progress

---

## Parallel Example: Foundational Phase

```text
# After T003 and T004 (backend schema + wiring) complete:
Task T005: "Integration tests for query overrides in tests/integration/test_query_overrides.py"
Task T006: "Unit tests for API client in tests/unit/test_api_client.py"
# Different test files with no dependencies -- run in parallel
```

## Parallel Example: User Story 3

```text
# After Foundational phase completes:
Task T015: "Unit tests for preset scenarios in tests/unit/test_scenarios.py"
Task T016: "Define preset scenarios and customer profiles in src/frontend/scenarios.py"
# Test validation and data definitions in separate files -- run in parallel
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (directory structure, dependencies)
2. Complete Phase 2: Foundational (backend overrides + API client connecting to local LangGraph workflow)
3. Complete Phase 3: User Story 1 (chat interface)
4. **STOP and VALIDATE**: Open browser, type a question, verify response from LangGraph agent
5. Deploy/demo if ready -- chat alone delivers a functional end-to-end experience

### Incremental Delivery

1. Setup + Foundational -> API client connects to local LangGraph workflow
2. Add User Story 1 -> Chat works end-to-end -> Demo (MVP!)
3. Add User Story 2 -> Trace inspection across 5 tabs -> Demo (transparent agent behavior)
4. Add User Story 3 -> Preset scenarios + sidebar controls -> Demo (full demo console)
5. Polish -> Approval workflow, validation -> Production-ready demo tool

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (chat UI -- T008-T011)
   - Developer B: User Story 3 data (T015, T016 -- scenarios, independent of chat)
3. After US1 complete:
   - Developer A: User Story 2 (observability -- T012-T014)
   - Developer B: User Story 3 wiring (T017, T018 -- sidebar into app)
4. Both finish -> Polish phase (T019-T021) together

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- All frontend state lives in `st.session_state` -- no database, no persistence across refreshes
- API client (`src/frontend/api_client.py`) is the single integration point between Streamlit and the LangGraph workflow
- Backend changes are minimal: two optional fields in `QueryRequest`, wiring in `/query` handler
- Total: 21 tasks across 6 phases (7 foundational + infrastructure, 4 US1, 3 US2, 4 US3, 3 polish)
