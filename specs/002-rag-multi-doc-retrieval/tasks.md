# Tasks: RAG Multi-Document Retrieval

**Input**: Design documents from `specs/002-rag-multi-doc-retrieval/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Included — TDD approach (write tests first, confirm they fail, then implement).

**Organization**: Tasks grouped by user story for independent implementation and testing. Knowledge base content creation is front-loaded as foundational work since the RAG system requires quality support documents with cross-domain overlap to demonstrate multi-document retrieval capabilities.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Add new dependencies, create directory structure, and configure test infrastructure.

- [X] T001 Add `ragas>=0.2` to dev dependencies in `pyproject.toml` under `[project.optional-dependencies]` and reinstall with `pip install -e ".[dev]"`
- [X] T002 [P] Create `tests/evals/` directory with `__init__.py` and `tests/evals/datasets/` subdirectory
- [X] T003 [P] Add `test-evals` target to `Makefile` that runs `pytest tests/evals/ -v`
- [X] T004 [P] Add CONFIDENCE_THRESHOLD, MIN_RESULT_COUNT, MAX_RETRIEVAL_ATTEMPTS, MAX_CONTEXT_DOCUMENTS, MULTI_QUERY_COUNT configuration parameters in `src/config.py`

---

## Phase 2: Foundational (Knowledge Base Content & Infrastructure)

**Purpose**: Create cross-domain knowledge base documents, extend graph state schema, and build core RAG pipeline components that ALL user stories depend on.

**Why content first**: The existing 14 knowledge base documents cover single-domain topics well, but cross-domain retrieval (US1), multi-query recall (US2), and adaptive retrieval (US3) all need documents with natural cross-domain overlap to function and be testable.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Knowledge Base Content — Billing Domain

- [X] T005 [P] Create support doc `docs/knowledge_base/billing/subscription-management.md` covering plan changes (upgrade/downgrade workflows), billing cycle adjustments, prorated charges for mid-cycle changes, and how plan tier affects account permissions and API rate limits
- [X] T006 [P] Create support doc `docs/knowledge_base/billing/payment-methods.md` covering supported payment methods (credit card, ACH, purchase orders), how to add/update payment info in account settings, payment security measures, PCI compliance notes, and failed payment consequences (grace period, account suspension)

### Knowledge Base Content — Technical Domain

- [X] T007 [P] Create support doc `docs/knowledge_base/technical/webhook-configuration.md` covering webhook endpoint setup, supported event types, payload format and signature verification, retry policies for failed deliveries (3 attempts at 5-min intervals then hourly for 24h), webhook logs, and plan-tier webhook limits
- [X] T008 [P] Create support doc `docs/knowledge_base/technical/sdk-quickstart.md` covering SDK installation for Python, Node.js, and Go, authentication setup with API keys, first API call walkthrough, common setup errors and solutions, and linking to API key management and rate limits docs
- [X] T009 [P] Create support doc `docs/knowledge_base/technical/rate-limits.md` covering rate limit tiers by pricing plan (Basic/Professional/Enterprise), rate limit response headers (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`), handling 429 responses with exponential backoff, requesting limit increases, and how plan upgrades affect rate limits

### Knowledge Base Content — Account Domain

- [X] T010 [P] Create support doc `docs/knowledge_base/account/team-management.md` covering inviting and removing team members, role assignments (admin, member, viewer) with permission details, per-plan seat limits and overage billing, transferring account ownership, and how team changes affect billing
- [X] T011 [P] Create support doc `docs/knowledge_base/account/data-export-procedures.md` covering data export formats (JSON, CSV), how to request a full export via dashboard and API, export size limits and processing time (up to 24h for large accounts), partial/filtered exports, and recommendation to export before cancellation
- [X] T012 [P] Create support doc `docs/knowledge_base/account/account-deletion.md` covering permanent account deletion process (distinct from cancellation), 90-day data retention window before permanent deletion, what data is deleted vs retained for legal compliance, billing implications (final invoice, outstanding balance), and re-registration after deletion

### Tests for Foundational Infrastructure ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T013 [P] Write unit tests for new SupportGraphState fields (classified_domains, search_queries, raw_retrieval_results with _accumulate reducer, merged_results, retrieval_confidence, retrieval_attempt, max_retrieval_attempts) in `tests/unit/test_state.py`
- [X] T014 [P] Write unit tests for new log event helpers (retrieval_plan, multi_retrieval, confidence_assessment, retrieval_retry, knowledge_gap event types and expected event_data fields) in `tests/unit/test_logger.py`
- [X] T015 [P] Write unit tests for query generator (domain-targeted query generation, query count matching MULTI_QUERY_COUNT config, output format with query/target_domain/aspect fields) in `tests/unit/test_query_generator.py`
- [X] T016 [P] Write unit tests for result merger (content-hash dedup removes duplicates, score-based ranking orders by similarity, MAX_CONTEXT_DOCUMENTS cap enforced, empty input handling) in `tests/unit/test_result_merger.py`
- [X] T017 [P] Write unit tests for confidence scorer (avg similarity calculation, result count threshold check, should_retry decision logic, boundary conditions at threshold) in `tests/unit/test_confidence.py`

### Implementation for Foundational Infrastructure

- [X] T018 Extend SupportGraphState with classified_domains, search_queries, raw_retrieval_results (with _accumulate reducer), merged_results, retrieval_confidence, retrieval_attempt, max_retrieval_attempts per data-model.md schema in `src/graph/state.py`
- [X] T019 [P] Add log event helpers for retrieval_plan, multi_retrieval, confidence_assessment, retrieval_retry, and knowledge_gap event types per data-model.md event schema in `src/observability/logger.py`
- [X] T020 [P] Implement LLM-based query generator using Claude structured output to produce domain-targeted search query variations in `src/rag/query_generator.py`
- [X] T021 [P] Implement result merger with content-hash deduplication, similarity-score ranking, and configurable document cap (MAX_CONTEXT_DOCUMENTS) in `src/rag/result_merger.py`
- [X] T022 [P] Implement confidence scorer that evaluates avg similarity score and result count against CONFIDENCE_THRESHOLD and MIN_RESULT_COUNT in `src/rag/confidence.py`
- [X] T023 Extend retriever to support multi-domain queries (`$in` metadata filter) and unfiltered fallback queries in `src/rag/retriever.py`

### RAGAS Evaluation Datasets

- [X] T024 [P] Create cross-domain evaluation dataset (5-8 cases: queries spanning 2-3 domains with ground_truth answers and expected_domains) in `tests/evals/datasets/cross_domain.json`
- [X] T025 [P] Create single-domain regression dataset (5-8 cases: single-domain queries to verify no performance regression) in `tests/evals/datasets/single_domain.json`
- [X] T026 [P] Create edge cases dataset (3-5 cases: sparse coverage, contradictory info, context overflow scenarios for adaptive retrieval testing) in `tests/evals/datasets/edge_cases.json`

**Checkpoint**: Knowledge base expanded from 14 to 22 documents with cross-domain coverage. State schema extended. Core RAG components (query generator, result merger, confidence scorer, retriever) built and tested. Evaluation datasets ready. User story implementation can now begin.

---

## Phase 3: User Story 1 — Cross-Domain Query Resolution (Priority: P1) 🎯 MVP

**Goal**: Queries spanning multiple domains retrieve documents from all applicable domains and produce a unified response with per-domain citations.

**Independent Test**: Submit `"I was charged twice and now my account is locked"` via `POST /query` and verify: (1) `classified_domains: ["billing", "account"]`, (2) citations reference sources from both domains, (3) single-domain queries still work without regression.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T027 [P] [US1] Write unit tests for supervisor multi-domain classification (single-domain returns one domain, dual-domain returns two, all-domains returns three, unknown routes to fallback) in `tests/unit/test_supervisor.py`
- [X] T028 [P] [US1] Write unit tests for retrieval_planner node (generates one search query per classified domain, sets retrieval_attempt=1, sets max_retrieval_attempts from config) in `tests/unit/test_retrieval_planner.py`
- [X] T029 [P] [US1] Write unit tests for multi_retriever node (executes queries against retriever, collects raw results, calls result merger, populates merged_results and retrieved_documents) in `tests/unit/test_multi_retriever.py`
- [X] T030 [P] [US1] Write unit tests for response_generator node (grounded response with per-document citations, domain attribution, citation includes domain/source/score fields, no citations when no results) in `tests/unit/test_response_generator.py`

### Implementation for User Story 1

- [X] T031 [US1] Modify supervisor to return classified_domains: list[str] via Claude structured output and route to retrieval_planner (classifiable) or fallback_handler (unknown) in `src/agents/supervisor.py`
- [X] T032 [US1] Implement retrieval_planner node that generates domain-targeted search queries using query_generator and initializes retrieval_attempt counter in `src/agents/retrieval_planner.py`
- [X] T033 [US1] Implement multi_retriever node that executes search queries via retriever with domain metadata filters, collects raw results, and calls result_merger for dedup/rank in `src/agents/multi_retriever.py`
- [X] T034 [US1] Implement response_generator node that prompts Claude with merged_results to generate grounded response with per-document citations including domain, source, and score in `src/agents/response_generator.py`
- [X] T035 [US1] Update validate_response to handle multi-domain citations and log final retrieval metrics in `src/agents/validate_response.py`
- [X] T036 [US1] Implement basic confidence_check node (evaluates merged_results, routes to response_generator when result count meets MIN_RESULT_COUNT) in `src/agents/confidence_check.py`
- [X] T037 [US1] Implement routing logic for supervisor conditional (retrieval_planner vs fallback_handler) and confidence_check conditional (response_generator vs multi_retriever) in `src/graph/routing.py`
- [X] T038 [US1] Build new graph topology: supervisor → retrieval_planner → multi_retriever → confidence_check → response_generator → validate_response, with fallback_handler branch, removing per-domain agent nodes in `src/graph/workflow.py`
- [X] T039 [US1] Update QueryResponse schema with classified_domains, retrieval_attempts, documents_retrieved, documents_after_dedup, retrieval_confidence metadata fields and citation domain/score fields in `src/api/schemas.py`
- [X] T040 [US1] Update `/query` endpoint to extract and return new metadata fields from graph state in `src/api/main.py`

### Integration Tests for User Story 1

- [X] T041 [US1] Write integration test for cross-domain query workflow (end-to-end graph execution with mocked LLM, verify multi-domain retrieval and citation domains) in `tests/integration/test_workflow.py`
- [X] T042 [US1] Write integration test for updated API response (POST /query returns classified_domains, retrieval_attempts, documents_retrieved, documents_after_dedup, retrieval_confidence, and citation domain/score) in `tests/integration/test_api.py`

**Checkpoint**: Cross-domain queries return unified responses with multi-domain citations. Single-domain queries still work without regression. System can be tested and demoed independently.

---

## Phase 4: User Story 2 — Multi-Query Retrieval for Improved Recall (Priority: P2)

**Goal**: Complex multi-facet queries generate multiple search variations to improve document recall, with deduplication of overlapping results. Simple queries bypass expansion.

**Independent Test**: Submit `"What happens to my data if I cancel mid-cycle and haven't exported my reports?"` and verify: (1) search_queries contains at least 2 distinct queries targeting different aspects, (2) combined results cover documents from multiple topics, (3) duplicates are removed.

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T043 [P] [US2] Write unit tests for multi-facet query expansion (complex query produces 2-3 aspect-targeted variations) and simple-query passthrough (simple query uses original query only, no forced expansion) in `tests/unit/test_query_generator.py`
- [X] T044 [P] [US2] Write integration tests for multi-query recall improvement (combined results cover more documents than single query) and dedup across overlapping results in `tests/integration/test_retriever.py`

### Implementation for User Story 2

- [X] T045 [US2] Enhance retrieval_planner with LLM-based multi-query generation: use Claude to produce 2-3 semantically diverse query variations per classified domain, each targeting a different aspect of the original question, in `src/agents/retrieval_planner.py`
- [X] T046 [US2] Add smart query expansion bypass in retrieval_planner: for simple single-facet queries, skip multi-query generation and use the original query directly to avoid forced overhead in `src/agents/retrieval_planner.py`
- [X] T047 [P] [US2] Add per-query result counts and dedup statistics to the multi_retrieval observation log event in `src/observability/logger.py`

**Checkpoint**: Multi-facet queries produce diverse search variations with improved recall. Simple queries bypass expansion. Duplicates are removed.

---

## Phase 5: User Story 3 — Confidence-Based Adaptive Retrieval (Priority: P3)

**Goal**: Low-quality retrieval results trigger automatic retry with progressively broader parameters. Persistent low confidence results in explicit knowledge gap acknowledgment rather than weakly-grounded responses.

**Independent Test**: Submit a query with sparse knowledge base coverage and verify: (1) system detects low-confidence initial results, (2) retries with increased k and relaxed domain filter, (3) if still insufficient after 3 attempts, response acknowledges the gap.

### Tests for User Story 3 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T048 [P] [US3] Write unit tests for confidence_check node retry logic (retry on low avg similarity, retry on low result count, proceed on high confidence, stop after MAX_RETRIEVAL_ATTEMPTS) in `tests/unit/test_confidence_check.py`
- [X] T049 [P] [US3] Write unit tests for retry parameter broadening (attempt 1: domain-filtered k=5, attempt 2: broadened k=10, attempt 3: no filter k=15) in `tests/unit/test_retrieval_planner.py`
- [X] T050 [P] [US3] Write unit tests for knowledge gap response generation (explicit acknowledgment, no citations, retrieval_confidence below threshold in response metadata) in `tests/unit/test_response_generator.py`

### Implementation for User Story 3

- [X] T051 [US3] Enhance confidence_check node with full retry decision logic using confidence scorer: evaluate avg similarity and result count, return Command(goto="multi_retriever") for retry or Command(goto="response_generator") to proceed, in `src/agents/confidence_check.py`
- [X] T052 [US3] Wire confidence_check retry loop into graph: confidence_check → multi_retriever (retry) with retrieval_attempt increment, capped at MAX_RETRIEVAL_ATTEMPTS in `src/graph/workflow.py`
- [X] T053 [US3] Update retrieval_planner to adjust search parameters on retry: attempt 2 increases k to 10 and broadens domain filter, attempt 3 removes domain filter and sets k to 15, per research.md retry strategy in `src/agents/retrieval_planner.py`
- [X] T054 [US3] Implement knowledge gap handling in response_generator: when retrieval_confidence remains below threshold after max attempts, generate explicit acknowledgment response per contracts/api.md knowledge gap format in `src/agents/response_generator.py`
- [X] T055 [P] [US3] Add confidence_assessment, retrieval_retry, and knowledge_gap observation log calls at appropriate points in confidence_check and response_generator nodes

### Integration Tests for User Story 3

- [X] T056 [US3] Write integration test for adaptive retrieval retry flow (low-confidence → retry with broader params → success) in `tests/integration/test_workflow.py`
- [X] T057 [US3] Write integration test for knowledge gap acknowledgment (low-confidence → max retries exhausted → gap response with no citations) in `tests/integration/test_workflow.py`

**Checkpoint**: Adaptive retrieval retries with progressively broader parameters. Knowledge gaps are surfaced honestly. High-confidence retrievals proceed without delay.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: RAGAS evaluation suite, ingestion updates, cleanup, and end-to-end validation.

- [X] T058 [P] Implement RAGAS evaluation test suite with faithfulness ≥ 0.8, answer_relevancy ≥ 0.7, context_precision ≥ 0.7, context_recall ≥ 0.7 assertions using `ragas.evaluate()` with `in_ci=True` in `tests/evals/test_rag_quality.py`
- [X] T059 [P] Update routing accuracy evaluation tests for multi-domain classification in `tests/evals/test_routing_accuracy.py`
- [X] T060 [P] Update document ingestion in `src/rag/ingest.py` to handle the 8 new knowledge base documents (ensure domain metadata is correctly set from directory structure)
- [X] T061 [P] Update `Makefile` seed target to re-ingest all knowledge base documents including the 8 new support docs
- [X] T062 [P] Remove unused per-domain agent files: `src/agents/billing_agent.py`, `src/agents/technical_agent.py`, `src/agents/account_agent.py` (replaced by unified response_generator pipeline)
- [X] T063 Update existing unit tests for refactored supervisor (multi-domain classification) and remove tests for deleted per-domain agents in `tests/unit/`
- [X] T064 Update integration tests for the new retrieval pipeline in `tests/integration/`
- [X] T065 Run full quickstart.md validation: `make up && make seed && make test-unit && make run`, test cross-domain and adaptive queries via curl, run `make test-evals`

---

## Phase 7: Security Layer (User Story 4 — Sensitive Query Escalation)

**Goal**: Add a dedicated `security_check` node between supervisor and retrieval_planner so sensitive queries (account takeover, fraud signals, future PII / plan-tier policies) bypass retrieval and route to a `escalation_handler` terminal node. This re-homes the escalation logic that was lost when the per-domain worker agents were removed in T062.

**Independent Test**: Send "I think someone hacked my account" and verify (1) `security_check` fires the `account_takeover` signal, (2) graph routes to `escalation_handler` (no retrieval, no response_generator LLM call), (3) `escalation_triggered` log event is emitted, (4) end-to-end latency under 1s.

### Data Model

- [ ] T066 [P] [US4] Extend `SupportGraphState` in `src/graph/state.py` with `security_signals: list[dict] | None`, `escalation_required: bool | None`, `escalation_reason: str | None` per data-model.md SecuritySignal/EscalationOutcome entries
- [ ] T067 [P] [US4] Add `log_security_check()` and `log_escalation_triggered()` helpers in `src/observability/logger.py` per data-model.md new event types

### security_check Node

- [ ] T068 [P] [US4] Write unit tests for rule-based signal detection in `tests/unit/test_security_check.py`: account-takeover phrases ("hacked", "unauthorized access", "someone logged in", "compromised", "didn't make this change") fire `account_takeover` signal with `severity="block"` and `action="escalate"`; non-sensitive queries return no signals
- [ ] T069 [P] [US4] Write unit tests for `security_check` node return value: `Command(goto="escalation_handler")` when any blocking signal fires, `Command(goto="retrieval_planner")` otherwise; state update writes `security_signals`, `escalation_required`, `escalation_reason`
- [ ] T070 [P] [US4] Write unit tests for policy gate latency: rule-based path completes in under 50ms (SC-008) — use a deterministic timing fixture, no LLM call on the rule-only path
- [ ] T071 [US4] Implement `src/agents/security_check.py` — pattern table for documented sensitive-query categories (start with `account_takeover`; design for additive policies), rule-based pre-check, optional LLM fallback for ambiguous cases; emit `security_check` log event with signals + action; return `Command(goto=...)` per signal severity. Ensure T068, T069, T070 pass.

### escalation_handler Node

- [ ] T072 [P] [US4] Write unit tests for `escalation_handler` in `tests/unit/test_escalation_handler.py`: response_text contains security-team contact instructions, citations is empty list, `escalation_triggered` log event has matching signal + reason
- [ ] T073 [US4] Implement `src/agents/escalation_handler.py` — produce a deterministic security-team-routing response from `escalation_reason` and `security_signals`, emit `escalation_triggered` log event, write final state. No LLM call. Ensure T072 passes.

### Graph Wiring

- [ ] T074 [US4] Update `src/graph/workflow.py`: insert `security_check` node between supervisor and retrieval_planner; add `escalation_handler` node with edge to END; update supervisor to route to `security_check` instead of `retrieval_planner`
- [ ] T075 [US4] Write integration test in `tests/integration/test_workflow.py`: account-takeover query → escalation path with no retrieval invocations (mock `multi_retriever.retrieve_documents_multi_domain` and assert it was not called); benign query → unchanged path through retrieval

### End-to-End Verification

- [ ] T076 [US4] Re-enable / restore `tests/evals/test_end_to_end.py::test_account_agent_triggers_escalation_for_takeover` so it asserts the new path: `escalation_triggered` event present, `routed_to_agent == "escalation_handler"`, citations is empty
- [ ] T077 [P] [US4] Add a routing accuracy eval in `tests/evals/test_routing_accuracy.py` covering 3+ takeover-phrasing variants and 3+ benign account queries; assert 100% correct policy gating per SC-007

**Checkpoint**: SC-007, SC-008, SC-009 satisfied. Adding a future policy category (e.g., PII redaction) requires only updates to `security_check.py` and its tests — no changes to retrieval, generation, or supervisor.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational — delivers MVP
- **US2 (Phase 4)**: Depends on US1 (enhances retrieval_planner and multi_retriever created in US1)
- **US3 (Phase 5)**: Depends on US1 (inserts confidence_check into pipeline from US1). Independent of US2.
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) — No dependencies on other stories
- **User Story 2 (P2)**: Depends on US1 (enhances nodes created in US1) — independently testable once US1 is complete
- **User Story 3 (P3)**: Depends on US1 (inserts into pipeline from US1) — independently testable once US1 is complete. Does NOT depend on US2.
- **User Story 4 (P2)**: Depends on the supervisor → retrieval_planner edge from US1. Independently testable once US1 is complete. Does NOT depend on US2 or US3 — adds a node *before* retrieval, so retrieval-quality work and policy work proceed on different paths.

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- RAG components before graph nodes
- Graph nodes before routing and workflow assembly
- Core implementation before integration tests
- Story complete before moving to next priority

### Parallel Opportunities

- **Phase 1**: T001–T004 can all run in parallel
- **Phase 2**: All knowledge base content (T005–T012) in parallel; all foundational tests (T013–T017) in parallel; all foundational implementations (T019–T022) in parallel after T018; all datasets (T024–T026) in parallel
- **Phase 3 (US1)**: T027–T030 (tests) in parallel; T032–T034 (new node implementations) in parallel
- **Phase 4 (US2)**: T043–T044 (tests) in parallel; T047 in parallel with T045–T046
- **Phase 5 (US3)**: T048–T050 (tests) in parallel; T055 in parallel with T051–T054
- **Phase 6**: T058–T062 can all run in parallel
- **Phase 7 (US4)**: T066–T067 (data model + logging) in parallel; T068–T070 (security_check tests) in parallel; T072 (escalation_handler tests) in parallel with T068–T071; T077 in parallel with T076
- US2, US3, and US4 can start in parallel after US1 completes (none of them depend on each other)

---

## Parallel Example: Foundational Tests (Phase 2)

```text
# Launch all foundational unit tests together (all [P], write before implementation):
Task T013: "Unit tests for new state fields in tests/unit/test_state.py"
Task T014: "Unit tests for new log event helpers in tests/unit/test_logger.py"
Task T015: "Unit tests for query generator in tests/unit/test_query_generator.py"
Task T016: "Unit tests for result merger in tests/unit/test_result_merger.py"
Task T017: "Unit tests for confidence scorer in tests/unit/test_confidence.py"
```

## Parallel Example: User Story 1 Nodes

```text
# After tests are written and failing, launch node implementations in parallel:
Task T031: "Modify supervisor in src/agents/supervisor.py"
Task T032: "Implement retrieval_planner in src/agents/retrieval_planner.py"
Task T033: "Implement multi_retriever in src/agents/multi_retriever.py"
Task T034: "Implement response_generator in src/agents/response_generator.py"

# Then sequentially (depend on nodes existing):
Task T037: "Implement routing in src/graph/routing.py"
Task T038: "Build graph topology in src/graph/workflow.py"
Task T039: "Update API schemas in src/api/schemas.py"
Task T040: "Update /query endpoint in src/api/main.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test with cross-domain curl commands from quickstart.md
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Knowledge base expanded, schemas ready, core components tested
2. Add User Story 1 → Cross-domain retrieval works → Deploy/Demo (MVP!)
3. Add User Story 2 → Better recall for complex queries → Deploy/Demo
4. Add User Story 3 → Adaptive retry prevents weak answers → Deploy/Demo
5. Polish → RAGAS evaluation, test updates, final validation → Final delivery

### Sequential Recommended Order

US2 and US3 both build on nodes created in US1, so sequential execution (P1 → P2 → P3) is recommended. Each story enhances the same files (retrieval_planner.py, multi_retriever.py, workflow.py) created in US1.

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Knowledge base docs follow existing style (headers, bullet points, tables, escalation criteria)
- New docs include natural cross-domain references for testing
- Each user story is independently completable and testable
- TDD: write tests first, verify they fail, then implement
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- RAGAS evaluation provides quantitative proof of grounding quality (hallucination guardrails)
