# Tasks: LangGraph Supervisor Prototype

**Input**: Design documents from `/specs/001-langgraph-supervisor-prototype/` and `/design/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/
**Tests**: Included — constitution Principle III (Test-First) mandates TDD.

**Organization**: Tasks are grouped by user story. The supervisor agent handles all responsibilities from `design/supervisor agent.md`: understand request, classify domain, decide RAG need, route to worker, validate response, decide escalation, return final answer. The LangGraph flow follows `design/LangGraph Flow.md`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Exact file paths included in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project scaffolding, Docker Compose, and dependency installation

- [X] T001 Create project directory structure with `src/__init__.py`, `src/agents/__init__.py`, `src/graph/__init__.py`, `src/rag/__init__.py`, `src/observability/__init__.py`, `src/api/__init__.py`, `src/db/__init__.py`, and `tests/unit/`, `tests/integration/`, `tests/evals/` directories
- [X] T002 Create `pyproject.toml` with all dependencies: langgraph, langchain-anthropic, langchain-postgres, langchain-openai, langchain-core, langchain-text-splitters, fastapi, uvicorn, psycopg, structlog, python-dotenv, pydantic-settings, and dev dependencies pytest, pytest-asyncio, httpx, pytest-cov
- [X] T003 [P] Create `docker-compose.yml` with `pgvector/pgvector:pg16` service on port 5432, named volume `pgdata`, healthcheck, and volume mount for `scripts/init.sql`
- [X] T004 [P] Create `scripts/init.sql` with `CREATE EXTENSION IF NOT EXISTS vector;` and the `observation_logs` table DDL from data-model.md
- [X] T005 [P] Create `.env.example` with ANTHROPIC_API_KEY, OPENAI_API_KEY, DATABASE_URL, LLM_MODEL, EMBEDDING_MODEL, LOG_LEVEL placeholders
- [X] T006 [P] Create `Makefile` with targets: up, down, seed, test, test-unit, test-int, run, all
- [X] T007 [P] Create `.gitignore` entries for `.env`, `__pycache__/`, `*.egg-info/`, `.pytest_cache/`, `pgdata/`
- [ ] T008 Install dependencies with `pip install -e ".[dev]"` and verify import of langgraph, langchain_anthropic, fastapi

**Checkpoint**: Project structure ready, Postgres running via `make up`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundational Phase

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T009 [P] Write unit tests for `SupportGraphState` TypedDict validation and `log_events` reducer in `tests/unit/test_state.py` — verify state accepts valid data, `add_messages` reducer works, `log_events` accumulates correctly
- [X] T010 [P] Write unit tests for observability helpers in `tests/unit/test_logger.py` — verify `log_llm_call()`, `log_retrieval()`, `log_routing_decision()`, `log_agent_response()` produce correctly shaped JSON events with all required fields per FR-008, FR-009, FR-010
- [X] T011 [P] Write unit tests for text chunking in `tests/unit/test_chunking.py` — verify `RecursiveCharacterTextSplitter` produces chunks within size limits (1000 chars) with overlap (200 chars)
- [X] T012 [P] Write unit tests for routing logic in `tests/unit/test_routing.py` — verify `route_query()` maps "billing"→"billing_agent", "technical"→"technical_agent", "account"→"account_agent", "unknown"→"fallback_handler"

### Implementation for Foundational Phase

- [X] T013 Create application config in `src/config.py` using pydantic-settings `BaseSettings` — load ANTHROPIC_API_KEY, OPENAI_API_KEY, DATABASE_URL, LLM_MODEL, EMBEDDING_MODEL, LOG_LEVEL from environment / `.env`
- [X] T014 Implement `SupportGraphState` TypedDict in `src/graph/state.py` — define all fields: query_id, query_text, messages (with `add_messages` reducer), classified_domain, confidence_rationale, current_node, retrieved_documents, response_text, citations, run_id, log_events (with accumulator reducer). Ensure T009 tests pass
- [X] T015 [P] Implement observability helpers in `src/observability/logger.py` — configure `structlog` for JSON output, implement `log_llm_call()`, `log_retrieval()`, `log_routing_decision()`, `log_agent_response()` that both emit structlog lines and return event dicts for state accumulation. Ensure T010 tests pass
- [X] T016 [P] Implement text chunking in `src/rag/chunking.py` — create function using `RecursiveCharacterTextSplitter` with chunk_size=1000, chunk_overlap=200. Ensure T011 tests pass
- [X] T017 [P] Implement routing logic in `src/graph/routing.py` — create `route_query(state: SupportGraphState) -> str` that maps classified_domain to node names, with "unknown"→"fallback_handler". Ensure T012 tests pass
- [X] T018 Implement database connection in `src/db/connection.py` — create function to get Postgres connection string from config, initialize pgvector extension, create `PGVectorStore` instance with OpenAI `text-embedding-3-small` embeddings and collection name `support_kb`
- [X] T019 [P] Create billing knowledge base documents in `docs/knowledge_base/billing/` — one markdown file per billing agent responsibility from `design/Billing Agent.md`:
  - `pricing-plans.md`: pricing tiers, plan features, charge explanations (supports "Explain charges" responsibility)
  - `invoice-policies.md`: billing cycles, invoice generation, payment methods, late payment policies (supports "Retrieve invoice policies" responsibility)
  - `cancellation-terms.md`: cancellation procedures, notice periods, prorated refunds, early termination fees (supports "Retrieve cancellation terms" responsibility)
  - `refund-eligibility.md`: refund criteria, timelines, subscription status checks, partial vs full refunds (supports "Check subscription status" and "Determine refund eligibility" responsibilities)
  - `payment-disputes.md`: dispute procedures, escalation paths, chargeback policies, when to escalate to human agent (supports "Escalate payment disputes" responsibility)
- [X] T019a [P] Create technical knowledge base documents in `docs/knowledge_base/technical/` — 3-5 markdown files: API key management, troubleshooting guides, integration setup, error codes reference
- [X] T019b [P] Create account knowledge base documents in `docs/knowledge_base/account/` — 3-5 markdown files: login procedures, MFA setup, permissions management, profile updates, account recovery
- [X] T020 Implement document ingestion in `src/rag/ingest.py` — read markdown files from `docs/knowledge_base/{domain}/`, chunk with `src/rag/chunking.py`, embed via OpenAI, store in pgvector with domain metadata. Make it runnable as `python -m src.rag.ingest`. Ensure idempotency (skip already-ingested docs)
- [X] T021 Implement retriever in `src/rag/retriever.py` — wrap `PGVectorStore.as_retriever()` with `search_type="similarity"`, `search_kwargs={"k": 5}`, and domain metadata filtering. Include observability logging via `log_retrieval()` for every retrieval call

### Integration Tests for Foundational Phase

- [X] T022 [P] Write integration test for document ingestion in `tests/integration/test_ingest.py` — ingest test documents into real pgvector, verify chunks appear in database, verify idempotency on re-run. Requires running Postgres
- [X] T023 [P] Write integration test for retriever in `tests/integration/test_retriever.py` — ingest test documents, query by domain, verify similarity scores returned, verify domain filtering works. Requires running Postgres

**Checkpoint**: Foundation ready — state schema, observability, RAG pipeline, routing logic all tested and working. User story implementation can now begin.

---

## Phase 3: User Story 1 — Supervisor Routes a Billing Query (Priority: P1) MVP

**Goal**: A billing-related query submitted to the supervisor is classified as "billing", routed to the billing worker agent, which retrieves relevant knowledge-base content and returns a grounded response with citations and an audit trail.

**Independent Test**: Send a billing query (e.g., "Why was I charged twice this month?") through the full graph and verify: (1) supervisor classifies as "billing", (2) billing agent retrieves relevant docs, (3) response includes at least one citation, (4) audit trail logs routing decision.

**Supervisor Responsibilities (from design/supervisor agent.md)**:
1. Understand user request (parse query text)
2. Classify domain (billing/technical/account/unknown)
3. Decide whether RAG is needed (yes for all worker routes)
4. Route to specialist worker (billing_agent)
5. Validate response (citations present, non-empty response)
6. Decide whether to escalate (low-confidence check)
7. Return final answer (with metadata and audit trail)

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T024 [P] [US1] Write unit tests for supervisor classification in `tests/unit/test_supervisor.py` — mock `ChatAnthropic` to return structured classification {"domain": "billing", "rationale": "..."}. Verify supervisor writes `classified_domain`, `confidence_rationale`, `current_node` to state. Verify routing decision log event is emitted. Verify supervisor handles LLM errors gracefully (FR edge case)
- [X] T025 [P] [US1] Write unit tests for billing agent in `tests/unit/test_billing_agent.py` — mock retriever to return fixed billing documents, mock LLM to return a response. Test all 5 responsibilities from `design/Billing Agent.md`:
  - Retrieve pricing docs/invoice policies/cancellation terms: verify retriever called with domain="billing", verify retrieved docs passed to LLM context
  - Check subscription status: verify agent handles subscription-related queries by retrieving refund-eligibility.md content
  - Explain charges: verify agent produces grounded explanation citing pricing-plans.md
  - Determine refund eligibility: verify agent reasons over refund criteria and returns eligibility assessment with citations
  - Escalate payment disputes: verify agent detects dispute queries and includes escalation guidance from payment-disputes.md
  - Verify `response_text` always has non-empty `citations` (RAG-first). Verify retrieval + LLM call log events emitted. Verify edge case: retriever returns no results → agent acknowledges gap instead of hallucinating
- [X] T026 [P] [US1] Write unit tests for response validation in `tests/unit/test_validate_response.py` — verify that responses with zero citations are flagged, non-empty responses pass, and low-confidence retrieval results are annotated with reduced confidence

### Implementation for User Story 1

- [X] T027 [US1] Implement supervisor agent in `src/agents/supervisor.py` — create `supervisor(state: SupportGraphState) -> Command` node function per design/supervisor agent.md: (1) understand request by extracting query_text from state, (2) classify domain using Claude `with_structured_output` for billing/technical/account/unknown, (3) log routing decision via `log_routing_decision()`, (4) return `Command(goto=route_query(state))` to route to the appropriate worker. Ensure T024 tests pass
- [X] T028 [US1] Implement billing agent in `src/agents/billing_agent.py` — create `billing_agent(state: SupportGraphState) -> dict` node function covering all 5 responsibilities from `design/Billing Agent.md`:
  1. Retrieve top-k docs from pgvector filtered by domain="billing" (covers: retrieve pricing docs, invoice policies, cancellation terms)
  2. Log retrieval via `log_retrieval()`
  3. Call Claude with system prompt and retrieved context. System prompt must instruct the LLM to:
     - **Retrieve & cite**: ground all answers in retrieved pricing, invoice, and cancellation documents
     - **Check subscription status**: identify subscription-related queries and provide status-aware answers from retrieved context
     - **Explain charges**: break down charges clearly using retrieved pricing/invoice documentation
     - **Determine refund eligibility**: reason over refund criteria from retrieved context and state eligibility with justification
     - **Escalate payment disputes**: detect dispute/chargeback queries and include escalation instructions (e.g., "this requires human review") from payment-disputes.md content
  4. Log LLM call via `log_llm_call()`
  5. Extract citations from retrieved docs (MUST be non-empty per RAG-first principle)
  6. Log agent response via `log_agent_response()`
  7. Return state updates: response_text, citations, retrieved_documents, log_events
  Ensure T025 tests pass
- [X] T029 [US1] Implement response validation in `src/agents/validate_response.py` — create `validate_response(state: SupportGraphState) -> dict` node function per design/supervisor agent.md "validate response" responsibility: (1) check citations are non-empty (RAG-first enforcement), (2) check response_text is non-empty, (3) flag low-confidence retrieval results (average score below threshold), (4) log validation result. Ensure T026 tests pass
- [X] T030 [US1] Implement fallback handler in `src/agents/fallback.py` — create `fallback_handler(state: SupportGraphState) -> dict` node function: (1) generate fallback response acknowledging inability to route, (2) set empty citations, (3) log agent_response event
- [X] T031 [US1] Implement LangGraph workflow in `src/graph/workflow.py` — build `StateGraph(SupportGraphState)` with nodes: supervisor, billing_agent, validate_response, fallback_handler. Add conditional edge from supervisor using `route_query()`. Add edge from billing_agent → validate_response → END. Add edge from fallback_handler → END. Compile the graph. Follow flow from design/LangGraph Flow.md: classify_intent → route_to_worker → [worker] → validate_response → END
- [X] T032 [US1] Implement FastAPI schemas in `src/api/schemas.py` — create Pydantic models: `QueryRequest` (query_text: str, session_id: str | None), `CitationResponse`, `QueryMetadata`, `QueryResponse` (query_id, response_text, agent, routing_rationale, citations, metadata) per contracts/api.md
- [X] T033 [US1] Implement FastAPI app in `src/api/main.py` — create FastAPI app with lifespan handler (init DB, vector store on startup). Implement `POST /query` endpoint that invokes the compiled graph and returns `QueryResponse`. Implement `GET /health` endpoint per contracts/api.md
- [X] T034 [US1] Write integration test for full workflow in `tests/integration/test_workflow.py` — run the full `StateGraph` with mocked LLM but real retriever (Docker Postgres). Send a billing query, verify end-to-end flow: supervisor classifies → billing_agent retrieves → validate_response checks → response returned with citations and routing rationale
- [X] T035 [US1] Write integration test for API endpoints in `tests/integration/test_api.py` — use FastAPI `TestClient` to POST a billing query, verify response schema matches contracts/api.md. GET /health, verify structure. Test 422 on missing query_text

**Checkpoint**: User Story 1 (MVP) is fully functional. Billing queries flow through supervisor → billing_agent → validate_response → response. All tests pass. Run `make up && make seed && make run` and test with `curl -X POST localhost:8000/query -H "Content-Type: application/json" -d '{"query_text":"Why was I charged twice?"}'`

---

## Phase 4: User Story 2 — Supervisor Routes a Technical Query (Priority: P2)

**Goal**: A technical support query is classified and routed to the technical worker agent, which retrieves relevant technical documentation and returns a step-by-step grounded response.

**Independent Test**: Send a technical query (e.g., "How do I reset my API key?") and verify: (1) supervisor classifies as "technical", (2) technical agent retrieves technical docs, (3) response includes citations from technical domain.

### Tests for User Story 2

- [X] T036 [P] [US2] Write unit tests for technical agent in `tests/unit/test_technical_agent.py` — same pattern as billing agent tests: mock retriever with technical docs, mock LLM, verify grounded response with citations, verify retrieval + LLM log events, verify no-results edge case

### Implementation for User Story 2

- [X] T037 [US2] Implement technical agent in `src/agents/technical_agent.py` — create `technical_agent(state: SupportGraphState) -> dict` following same pattern as billing_agent but filtering retriever by domain="technical". Ensure T036 tests pass
- [X] T038 [US2] Add technical_agent node to graph in `src/graph/workflow.py` — add node, add conditional edge route from supervisor, add edge to validate_response → END
- [X] T039 [US2] Extend integration test in `tests/integration/test_workflow.py` — add test case sending a technical query through the graph, verify routing to technical_agent, verify technical domain retrieval

**Checkpoint**: User Stories 1 AND 2 both work independently. Billing and technical queries correctly routed.

---

## Phase 5: User Story 3 — Supervisor Routes an Account Query (Priority: P3)

**Goal**: An account management query is classified and routed to the account worker agent, which retrieves relevant account documentation and returns a grounded response. The account agent handles login, MFA, permissions, and security questions per `design/Account Agent.md`. It MUST never expose sensitive data (passwords, account numbers, SSNs, security question answers) and MUST escalate account takeover concerns.

**Independent Test**: Send account queries (e.g., "How do I set up MFA?", "How do I update my email address?") and verify: (1) supervisor classifies as "account", (2) account agent retrieves account docs, (3) response includes citations from account domain, (4) no sensitive data leaks in response text. Send an account takeover query and verify escalation metadata is set.

**Account Agent Responsibilities (from design/Account Agent.md)**:
1. Handle login — password reset, login troubleshooting, locked account recovery
2. Handle MFA — setup, troubleshooting, recovery codes
3. Handle permissions — role management, access control
4. Handle security questions — setup, reset, best practices
5. Never expose sensitive data — no raw credentials, account numbers, SSNs, or security question answers in responses
6. Escalate account takeover concerns — detect and flag unauthorized access reports

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T040 [P] [US3] Write unit tests for account agent basic RAG behavior in `tests/unit/test_account_agent.py` — mock retriever with account domain docs (login procedures, MFA guides, permissions docs, security question policies), mock LLM. Verify: (1) grounded response with non-empty citations (RAG-first), (2) retrieval + LLM call log events emitted, (3) domain filter set to "account", (4) edge case when retriever returns no results — agent acknowledges gap instead of hallucinating
- [X] T041 [P] [US3] Write unit tests for sensitive data protection in `tests/unit/test_account_agent.py` — mock retriever to return docs containing sensitive field patterns (passwords, account numbers, SSN-like patterns, security question answers). Verify: (1) response_text does NOT contain sensitive data patterns (regex check for SSN format, password hashes, raw credentials), (2) system prompt instructs the LLM to never include credentials or PII in responses, (3) citations may reference source docs but chunk_text is sanitized
- [X] T042 [P] [US3] Write unit tests for account takeover escalation in `tests/unit/test_account_agent.py` — verify: (1) queries containing takeover keywords ("someone accessed my account", "unauthorized login", "account compromised", "I didn't make this change") set an `escalation_flag` in the response metadata, (2) escalation response includes a clear message directing the customer to immediate support, (3) escalation events are logged with event_type "escalation_triggered"

### Implementation for User Story 3

- [X] T043 [US3] Create account domain knowledge base documents in `docs/knowledge_base/account/` — write 5 markdown files aligned with `design/Account Agent.md` responsibilities:
  - `login-procedures.md`: password reset steps, login troubleshooting, locked account recovery, supported authentication methods
  - `mfa-setup.md`: MFA enrollment flow, supported methods (TOTP, SMS), recovery codes generation, MFA troubleshooting (lost device, code not working)
  - `permissions-management.md`: user roles and access levels, how to request/grant/revoke permissions, admin vs regular user capabilities
  - `security-questions.md`: setting up security questions, resetting them, best practices for strong answers, when security questions are prompted
  - `account-takeover-policy.md`: what to do if account is compromised, immediate steps for users, escalation procedures, how support team handles takeover reports
- [X] T044 [US3] Implement account agent in `src/agents/account_agent.py` — create `account_agent(state: SupportGraphState) -> dict` node function: (1) retrieve top-k docs from pgvector filtered by domain="account", (2) log retrieval via `log_retrieval()`, (3) call Claude with account-specific system prompt that covers login/MFA/permissions/security questions AND includes strict instruction to never expose passwords, account numbers, SSNs, or security question answers in the response, (4) detect account takeover indicators in query_text (keyword matching for "unauthorized", "compromised", "someone accessed", "didn't make this change", "account stolen") — if detected, set escalation metadata and prepend escalation guidance to response, (5) log LLM call via `log_llm_call()`, (6) extract citations from retrieved docs, (7) write response_text, citations, retrieved_documents, log_events to state. Ensure T040, T041, T042 tests pass
- [X] T045 [US3] Add account_agent node to graph in `src/graph/workflow.py` — add `account_agent` node, add conditional edge route from supervisor for domain="account", add edge from account_agent → validate_response → END
- [X] T046 [US3] Extend integration test in `tests/integration/test_workflow.py` — add test cases: (1) send account query (e.g., "How do I set up MFA?") through the graph, verify supervisor routes to account_agent, verify account domain retrieval, verify grounded response with citations; (2) send account takeover query (e.g., "Someone logged into my account without my permission"), verify escalation metadata is set and escalation event is logged; (3) verify no sensitive data patterns appear in any account agent response text

**Checkpoint**: All three domain agents (billing, technical, account) work independently. SC-004 satisfied (3 domains with grounded responses). Account agent enforces sensitive data protection and escalation for takeover concerns.

---

## Phase 6: User Story 4 — Supervisor Handles Ambiguous or Multi-Domain Queries (Priority: P2)

**Goal**: Queries that span multiple domains or don't clearly fit any domain are handled gracefully — the supervisor either selects a primary domain with logged reasoning, or returns a fallback response.

**Independent Test**: Send ambiguous queries (e.g., "I was charged twice and my account is locked") and verify: (1) supervisor makes a clear routing decision with reasoning logged, (2) unclassifiable queries return a fallback response rather than guessing.

### Tests for User Story 4

- [X] T047 [P] [US4] Write unit tests for ambiguous query handling in `tests/unit/test_supervisor.py` — add test cases: (1) multi-domain query returns a valid classification with detailed rationale, (2) unclassifiable query sets domain to "unknown" and routes to fallback, (3) supervisor never returns an empty classified_domain
- [X] T048 [P] [US4] Write unit tests for fallback handler edge cases in `tests/unit/test_fallback.py` — verify fallback returns acknowledgement, sets empty citations (not a failure for fallback), logs event, handles the "no relevant documents" edge case from spec

### Implementation for User Story 4

- [X] T049 [US4] Enhance supervisor classification prompt in `src/agents/supervisor.py` — update the structured output prompt to handle ambiguous queries: instruct the LLM to select the primary domain when query spans multiple areas, provide detailed rationale for the choice, and classify as "unknown" only when genuinely unroutable. Ensure T047 tests pass
- [X] T050 [US4] Verify fallback handler covers all edge cases in `src/agents/fallback.py` — ensure fallback response includes the original query text in its acknowledgement, and response clearly states the system cannot confidently route rather than providing a generic error. Ensure T048 tests pass
- [X] T051 [US4] Add integration test for ambiguous queries in `tests/integration/test_workflow.py` — send a multi-domain query through the real graph, verify the supervisor makes a decision (not crash), response includes routing rationale. Send an unroutable query, verify fallback handler fires

**Checkpoint**: Supervisor robustly handles all query types — clean routing for single-domain, reasoned routing for ambiguous, graceful fallback for unroutable.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Eval suite, error handling edge cases, documentation validation

- [X] T052 [P] Validate billing agent handles all 5 design responsibilities end-to-end — run the full graph with seeded billing knowledge base and verify each responsibility from `design/Billing Agent.md`:
  - Send a pricing query (e.g., "What are your pricing tiers?") → verify response cites pricing-plans.md
  - Send an invoice query (e.g., "When is my next invoice?") → verify response cites invoice-policies.md
  - Send a cancellation query (e.g., "What's your cancellation policy?") → verify response cites cancellation-terms.md
  - Send a refund query (e.g., "Am I eligible for a refund?") → verify response reasons over refund-eligibility.md
  - Send a dispute query (e.g., "I want to dispute a charge") → verify response includes escalation guidance from payment-disputes.md
- [X] T053 [P] Validate account agent handles all design responsibilities end-to-end — run the full graph with seeded account knowledge base and verify each responsibility from `design/Account Agent.md`:
  - Send a login query (e.g., "How do I reset my password?") → verify response cites login-procedures.md
  - Send an MFA query (e.g., "How do I set up two-factor authentication?") → verify response cites mfa-setup.md
  - Send a permissions query (e.g., "How do I grant admin access to a team member?") → verify response cites permissions-management.md
  - Send a security questions query (e.g., "How do I change my security questions?") → verify response cites security-questions.md
  - Send a takeover query (e.g., "I think someone hacked my account") → verify escalation fires and response cites account-takeover-policy.md
  - Verify NO response contains sensitive data (passwords, SSNs, account numbers)
- [X] T054 [P] Create routing accuracy eval suite in `tests/evals/test_routing_accuracy.py` — define 9+ test queries (3 per domain: billing, technical, account) plus 3 ambiguous queries. Mark with `@pytest.mark.eval`. Run against real LLM, assert >= 90% correct routing (SC-001). Assert every response includes at least one citation (SC-002). Include at least one account takeover query to verify escalation fires correctly
- [X] T055 [P] Add error handling for LLM failures in `src/agents/supervisor.py` and worker agents — catch LLM API errors (timeout, rate limit, auth failure), return structured error response with run_id for debugging rather than crashing (spec edge case). Log error events
- [X] T056 [P] Add error handling for retriever failures in `src/rag/retriever.py` — handle database connection errors, empty result sets. When retriever returns no documents, worker should acknowledge the gap (spec edge case: "acknowledge the gap rather than hallucinate")
- [ ] T057 Validate end-to-end quickstart flow — follow `specs/001-langgraph-supervisor-prototype/quickstart.md` step by step: `make up` → `pip install -e ".[dev]"` → `make seed` → `make run` → curl billing query → curl account query → curl health check. Verify all steps succeed
- [ ] T058 [P] Run full test suite — execute `make test` and verify all unit, integration tests pass. Execute `make test-int` with Docker Postgres running

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - US1 (Phase 3): Can start after Phase 2 — no dependencies on other stories
  - US2 (Phase 4): Can start after Phase 2 — independent of US1 but benefits from completing US1 first (reuses worker pattern)
  - US3 (Phase 5): Can start after Phase 2 — independent, follows same worker pattern as US1/US2 but adds security constraints (sensitive data protection) and escalation logic (account takeover detection) unique to the account domain
  - US4 (Phase 6): Can start after Phase 2 — benefits from having all 3 workers available for testing ambiguous routing
- **Polish (Phase 7)**: Depends on all user stories being complete

### Within Each User Story

- Tests MUST be written and FAIL before implementation (constitution Principle III)
- Agents depend on state schema, observability, and retriever (Phase 2)
- Graph workflow depends on all agents for that story being implemented
- API endpoints depend on graph workflow being complete
- Integration tests require Docker Postgres running

### Parallel Opportunities

- T003, T004, T005, T006, T007 (Setup) — all parallel, different files
- T009, T010, T011, T012 (Foundational tests) — all parallel, different test files
- T015, T016, T017 (Foundational impl) — all parallel after T014 state schema
- T024, T025, T026 (US1 tests) — all parallel, different test files
- T036 (US2 test), T040/T041/T042 (US3 tests) — parallel with each other and with US1 implementation
- T052, T053, T054, T055, T056 (Polish) — all parallel, different files

---

## Parallel Example: User Story 3 (Account Agent)

```bash
# Launch all US3 tests together (write tests first):
Task T040: "Unit tests for account agent basic RAG in tests/unit/test_account_agent.py"
Task T041: "Unit tests for sensitive data protection in tests/unit/test_account_agent.py"
Task T042: "Unit tests for account takeover escalation in tests/unit/test_account_agent.py"

# Then sequential implementation:
Task T043: "Account domain KB docs in docs/knowledge_base/account/"
Task T044: "Account agent in src/agents/account_agent.py"
Task T045: "Add account_agent node to graph in src/graph/workflow.py"
Task T046: "Integration tests for account agent in tests/integration/test_workflow.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test billing query end-to-end
5. Demo with `make up && make seed && make run`

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add User Story 1 → Test billing queries → MVP!
3. Add User Story 2 → Test technical queries → Two domains working
4. Add User Story 3 → Test account queries (login, MFA, permissions, security, escalation) → All three domains (SC-004)
5. Add User Story 4 → Test ambiguous queries → Robust routing
6. Polish → Eval suite validates SC-001 (>= 90% accuracy)

### Key Files by Priority

| Priority | File | Purpose |
|---|---|---|
| Critical | `src/graph/state.py` | Shared state schema — everything depends on this |
| Critical | `src/agents/supervisor.py` | Core routing logic — the supervisor's brain |
| Critical | `src/graph/workflow.py` | Graph wiring — connects all nodes |
| Critical | `src/rag/retriever.py` | RAG pipeline — workers depend on this |
| Critical | `docs/knowledge_base/billing/` | Billing KB — 5 docs covering all billing responsibilities |
| High | `src/agents/billing_agent.py` | First worker (MVP) — covers 5 responsibilities from design/Billing Agent.md |
| High | `src/agents/validate_response.py` | Response quality gate |
| High | `src/api/main.py` | FastAPI entry point |
| Medium | `src/agents/technical_agent.py` | Second worker |
| Medium | `src/agents/account_agent.py` | Third worker — handles login, MFA, permissions, security questions; enforces sensitive data protection and account takeover escalation |
| Medium | `src/agents/fallback.py` | Edge case handling |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Constitution Principle III (Test-First) is NON-NEGOTIABLE — write tests first, confirm fail, then implement
- Constitution Principle I (RAG-First) — every worker MUST retrieve before responding, tests assert non-empty citations
- Constitution Principle IV (Observability) — every LLM call and retrieval call MUST emit structured log events
- Supervisor responsibilities from `design/supervisor agent.md`: understand request, classify domain, decide RAG need, route to worker, validate response, decide escalation, return final answer
- Billing agent responsibilities from `design/Billing Agent.md`: retrieve pricing docs/invoice policies/cancellation terms, check subscription status, explain charges, determine refund eligibility, escalate payment disputes
- Account agent responsibilities from `design/Account Agent.md`: handle login/MFA/permissions/security questions, never expose sensitive data, escalate account takeover concerns
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
