---
description: "Task list for Agent Business Action Tools implementation"
---

# Tasks: Agent Business Action Tools

**Input**: Design documents from `specs/003-agent-action-tools/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/api.md ✅, quickstart.md ✅, design/tool-guardrail-checks.md ✅

**Tests**: TDD is required per the constitution (Principle III). Tests are written first and must FAIL before implementation begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Exact file paths are included in every task description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create directory structure and stub files needed before any implementation begins.

- [X] T001 Create src/tools/ module with __init__.py files: `src/tools/__init__.py`, `src/tools/definitions/__init__.py`, `src/tools/backends/__init__.py`
- [X] T002 [P] Create empty stub files: `src/tools/registry.py`, `src/tools/guardrails.py`, `src/tools/executor.py`, `src/tools/audit.py`, `src/tools/approval.py`
- [X] T003 [P] Create empty stub files for new agent nodes: `src/agents/action_planner.py`, `src/agents/action_executor.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core tool infrastructure — registry, all nine guardrail check functions (per `design/tool-guardrail-checks.md`), executor pipeline, audit helpers, state schema, config, and observability. Must be complete before ANY user story begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests (write first — must FAIL before implementation)

- [X] T004 [P] Write failing unit tests for ToolDefinition dataclass and registry operations (get_registry, get_tool, get_tool_descriptions, allow-list filtering) in `tests/unit/test_registry.py`
- [X] T005 [P] Write failing unit tests for all nine guardrail check functions from `design/tool-guardrail-checks.md`: `validate_agent_allowlist` (unknown agent rejected), `validate_params` (bad schema rejected), `validate_customer_id` (mismatched ID blocked), `check_risk_level` (read-only and low pass through), `check_dollar_cap` (over-cap blocked), `check_refund_eligibility` (cancelled/pending blocked, shipped/delivered pass), `check_rate_limit` (sliding window counts), `check_idempotency` (duplicate key blocked), `check_requires_approval` (high-risk returns pending_approval) in `tests/unit/test_guardrails.py`
- [X] T006 [P] Write failing unit tests for execute_tool() wrapper (success path, each blocked path with correct block_reason, failed path, ToolResult dataclass fields) in `tests/unit/test_executor.py`
- [X] T007 [P] Write failing unit tests for audit logging helpers (log_tool_attempt, log_tool_success, log_tool_blocked, log_tool_failed emit correct structlog event types and required fields per contracts/api.md) in `tests/unit/test_audit.py`

### Implementation — Registry

- [X] T008 Implement ToolDefinition dataclass (name, description, input_schema, output_schema, risk_level, execute_fn, rate_limit, dollar_cap, allowed_agents) and registry functions (get_registry, get_tool, get_tool_descriptions with JSON Schema output) in `src/tools/registry.py`

### Implementation — Guardrail Checks (one task per check from `design/tool-guardrail-checks.md`)

- [X] T009 Implement `validate_agent_allowlist(agent_type: str, tool_name: str, allowed_agents: list[str]) -> None` — raises UnknownToolError if agent_type not in tool's allowed_agents list (FR-001a) in `src/tools/guardrails.py`
- [X] T010 Implement `validate_params(parameters: dict, input_schema: type[BaseModel]) -> BaseModel` — parses parameters with Pydantic, raises InvalidParamsError with field-level detail on validation failure (FR-006) in `src/tools/guardrails.py`
- [X] T011 Implement `validate_customer_id(parameters: dict, session_customer_id: str) -> None` — raises CustomerIdMismatchError if customer_id in parameters does not match the session's customer_id (FR-006a) in `src/tools/guardrails.py`
- [X] T012 Implement `check_risk_level(risk_level: str) -> str` — returns "proceed" for read-only/low, returns "requires_approval" for high, raises ValueError for unrecognized tier (FR-002, FR-004) in `src/tools/guardrails.py`
- [X] T013 Implement `check_dollar_cap(parameters: dict, dollar_cap: float | None) -> None` — raises DollarCapError if parameters["amount"] exceeds dollar_cap; no-op if dollar_cap is None (FR-008) in `src/tools/guardrails.py`
- [X] T014 Implement `check_refund_eligibility(order_id: str) -> None` — looks up order via mock_orders backend, raises RefundIneligibleError with reason if status is "cancelled" or "pending"; passes for "shipped" or "delivered" (FR-008a) in `src/tools/guardrails.py`
- [X] T015 Implement `check_rate_limit(session_id: str, tool_name: str, limit: int) -> None` — maintains in-memory dict mapping (session_id, tool_name) to list of timestamps, raises RateLimitError if call count in last 60 seconds reaches limit (FR-007) in `src/tools/guardrails.py`
- [X] T016 Implement `check_idempotency(session_id: str, tool_name: str, parameters: dict) -> str` — generates deterministic key from (session_id, tool_name, sorted parameters), raises DuplicateToolCallError if key was seen in this session; returns new key on first call (FR-008b) in `src/tools/guardrails.py`
- [X] T017 Implement `check_requires_approval(tool_name: str, parameters: dict, session_id: str) -> ApprovalRequest` — called only when check_risk_level returns "requires_approval"; creates and stores an ApprovalRequest with UUID, timestamps, and APPROVAL_TIMEOUT_SECONDS expiry (FR-005) in `src/tools/guardrails.py`

### Implementation — Executor, Audit, Infrastructure

- [X] T018 Implement `execute_tool(tool_name, parameters, session_id, agent_type) -> ToolResult` orchestrating the nine checks in order: validate_agent_allowlist → validate_params → validate_customer_id → check_rate_limit → check_idempotency → check_dollar_cap → check_refund_eligibility → check_risk_level → check_requires_approval (high-risk) or tool.execute_fn (proceed), then log audit event in `src/tools/executor.py`
- [X] T019 Implement audit logging helpers (log_tool_attempt, log_tool_success, log_tool_blocked, log_tool_failed, log_approval_requested, log_approval_resolved) using structlog with all required fields from contracts/api.md in `src/tools/audit.py`
- [X] T020 Add tool-related state fields (tool_calls, tool_results with Annotated accumulator, pending_approvals, action_taken) to SupportGraphState in `src/graph/state.py`
- [X] T021 [P] Add observability event helpers for new event types (tool_call_attempt, tool_call_success, tool_call_blocked, tool_call_failed, approval_requested, approval_resolved) to `src/observability/logger.py`
- [X] T022 [P] Add TOOL_RATE_LIMIT_PER_MINUTE (default 10), TOOL_DOLLAR_CAP (default 100.0), APPROVAL_TIMEOUT_SECONDS (default 300), TOOL_EXECUTION_ENABLED (default True) to `src/config.py`

**Checkpoint**: Foundation ready — all nine guardrail checks implemented and tested, user story implementation can now begin

---

## Phase 3: User Story 1 — Autonomous Low-Risk Action Execution (Priority: P1) 🎯 MVP

**Goal**: Agent autonomously executes order status lookup and support ticket creation, includes real results in response, and logs every action to the audit trail — no human intervention required.

**Independent Test**: POST `{"query_text": "What is the status of my order ORD-12345?"}` to `/query`. Verify: (1) agent calls `order_status_lookup`, (2) response contains order status "shipped", (3) audit trail has a `tool_call_success` event. Then POST a billing issue query and verify a ticket ID appears in the response.

### Tests (write first — must FAIL before implementation)

- [X] T023 [P] [US1] Write failing unit tests for mock order database (lookup by ID returns deterministic data for ORD-12345 through ORD-12349, order-not-found raises, fail_mode triggers service-unavailable) in `tests/unit/test_mock_backends.py`
- [X] T024 [P] [US1] Write failing unit tests for mock ticketing system (create_ticket returns TKT-NNN ID, counter increments, ticket stored in memory) in `tests/unit/test_mock_backends.py`
- [X] T025 [P] [US1] Write failing unit tests for order_status_lookup tool (success with OrderStatusOutput for valid ID, unknown order_id returns error result) in `tests/unit/test_order_status.py`
- [X] T026 [P] [US1] Write failing unit tests for create_support_ticket tool (all fields set, defaults applied for priority/category, returns CreateTicketOutput with ticket_id) in `tests/unit/test_create_ticket.py`
- [X] T027 [P] [US1] Write failing unit tests for action_planner node (returns tool_calls list for actionable query, returns empty list for non-actionable query, uses only allow-listed tools) in `tests/unit/test_action_planner.py`
- [X] T028 [P] [US1] Write failing unit tests for action_executor node (calls execute_tool for each planned tool call, accumulates tool_results, sets action_taken=True on success) in `tests/unit/test_action_executor.py`

### Implementation

- [X] T029 [P] [US1] Implement mock order database with 5 deterministic orders (ORD-12345 through ORD-12349 with statuses: shipped, delivered, pending, cancelled, shipped) and configurable fail_mode parameter in `src/tools/backends/mock_orders.py`
- [X] T030 [P] [US1] Implement mock ticketing system with counter-based TKT-NNN ID generation and in-memory ticket storage in `src/tools/backends/mock_tickets.py`
- [X] T031 [US1] Implement OrderStatusInput/OrderStatusOutput Pydantic schemas and order_status_lookup(params) function calling mock_orders backend in `src/tools/definitions/order_status.py`
- [X] T032 [US1] Implement CreateTicketInput/CreateTicketOutput Pydantic schemas and create_support_ticket(params) function calling mock_tickets backend in `src/tools/definitions/create_ticket.py`
- [X] T033 [US1] Register order_status_lookup (risk_level="read-only", allowed_agents=["support"]) and create_support_ticket (risk_level="low", allowed_agents=["support"]) in the tool registry dict in `src/tools/registry.py`
- [X] T034 [US1] Implement action_planner node: reads query_text + response_text + merged_results, calls LLM with ToolCallPlan structured output schema (action_needed, list[PlannedToolCall]), writes tool_calls to state in `src/agents/action_planner.py`
- [X] T035 [US1] Implement action_executor node: iterates tool_calls, calls execute_tool() for each passing agent_type from state, accumulates tool_results, sets action_taken, appends tool result summaries to response_text in `src/agents/action_executor.py`
- [X] T036 [US1] Modify response_generator to detect tool-actionable queries and set action_needed flag in returned state dict in `src/agents/response_generator.py`
- [X] T037 [US1] Add conditional routing from response_generator to action_planner (if action_needed) and from action_executor to validate_response in `src/graph/workflow.py` and `src/graph/routing.py`
- [X] T038 [US1] Extend POST /query response Pydantic schema with tool_calls (list[ToolCallResult]) and action_taken (bool) fields in `src/api/schemas.py` and `src/api/main.py`
- [X] T039 [US1] Write integration test for autonomous order status lookup and ticket creation through the full graph in `tests/integration/test_tool_workflow.py`

**Checkpoint**: US1 fully functional and independently testable — MVP delivered

---

## Phase 4: User Story 2 — Human Approval for High-Risk Actions (Priority: P1)

**Goal**: Refund requests are prepared and queued but NOT executed until a human reviewer explicitly approves via the `/approvals` API. Rejections and timeouts are handled correctly.

**Independent Test**: POST `{"query_text": "I need a refund for order ORD-12345, the product was defective"}` to `/query`. Verify: (1) response includes `pending_approvals` with a refund entry, (2) refund is NOT processed yet, (3) POST to `/approvals/{id}/approve` causes the refund to execute and returns a refund record.

### Tests (write first — must FAIL before implementation)

- [X] T040 [P] [US2] Write failing unit tests for in-memory approval queue (create returns ApprovalRequest with UUID and expiry, approve transitions to approved and executes, reject transitions to rejected, expire_pending transitions expired entries) in `tests/unit/test_approval.py`
- [X] T041 [P] [US2] Write failing unit tests for mock payment processor (lookup payment by order_id, create refund record with REF-NNN ID, fail_mode triggers service-unavailable) in `tests/unit/test_mock_backends.py`
- [X] T042 [P] [US2] Write failing unit tests for issue_refund tool (approval-required path returns pending_approval status, ineligible order statuses "cancelled"/"pending" are blocked by check_refund_eligibility guardrail before tool runs) in `tests/unit/test_issue_refund.py`

### Implementation

- [X] T043 [US2] Implement ApprovalRequest dataclass and in-memory approval queue (create_approval, get_approval, approve, reject, expire_pending, list_pending) with APPROVAL_TIMEOUT_SECONDS config in `src/tools/approval.py`
- [X] T044 [US2] Implement mock payment processor with 3 payment records (PAY-001 to PAY-003 linked to orders) and refund creation with REF-NNN ID generation in `src/tools/backends/mock_payments.py`
- [X] T045 [US2] Implement IssueRefundInput/IssueRefundOutput Pydantic schemas and issue_refund(params) function calling mock_payments backend — order status eligibility is enforced upstream by check_refund_eligibility guardrail, not re-validated here in `src/tools/definitions/issue_refund.py`
- [X] T046 [US2] Register issue_refund tool in the registry with risk_level="high", dollar_cap=TOOL_DOLLAR_CAP, allowed_agents=["support"] in `src/tools/registry.py`
- [X] T047 [US2] Add GET /approvals, POST /approvals/{id}/approve, POST /approvals/{id}/reject endpoints to `src/api/main.py`
- [X] T048 [US2] Add ApprovalListResponse, ApproveRequest, RejectRequest, ApprovalResponse, and ApprovalItem Pydantic schemas to `src/api/schemas.py`
- [X] T049 [US2] Extend POST /query response Pydantic schema with pending_approvals (list[ApprovalItem]) field in `src/api/schemas.py`
- [X] T050 [US2] Write integration test for full approval workflow (POST /query → pending approval in response → POST /approvals/{id}/approve → refund executed and recorded) in `tests/integration/test_approval_api.py`

**Checkpoint**: US2 fully functional — high-risk actions gated by human approval

---

## Phase 5: User Story 3 — Multi-Tool Composition for Complex Issues (Priority: P2)

**Goal**: Agent plans and executes sequences of tools, using outputs from earlier tools to inform later ones, and degrades gracefully when any step fails.

**Independent Test**: POST `{"query_text": "My account was double-charged, please look into it and open a ticket"}` to `/query`. Verify: (1) agent calls order lookup, (2) then creates a ticket referencing order details from step 1, (3) both tool calls appear in audit trail in sequence.

### Tests (write first — must FAIL before implementation)

- [X] T051 [US3] Write failing unit tests for multi-tool sequencing in action_executor (second tool call receives first tool's result in context, results accumulate in tool_results list) in `tests/unit/test_action_executor.py`
- [X] T052 [US3] Write failing unit tests for partial failure handling (action_executor reports succeeded steps and skips tool calls that depend on a failed step) in `tests/unit/test_action_executor.py`

### Implementation

- [X] T053 [US3] Update action_executor to include prior tool_results in the context passed to each subsequent execute_tool() call in `src/agents/action_executor.py`
- [X] T054 [US3] Update action_executor to handle partial failures gracefully — collect errors per tool, skip dependent calls, append partial-success summary to response_text in `src/agents/action_executor.py`
- [X] T055 [US3] Write integration test for multi-step tool workflow (order status lookup → create support ticket with order details from step 1, both in audit trail) in `tests/integration/test_tool_workflow.py`

**Checkpoint**: US3 functional — multi-tool sequences resolve in a single interaction

---

## Phase 6: User Story 4 — Safety Guardrails Block Harmful Actions (Priority: P1)

**Goal**: All nine guardrail checks from `design/tool-guardrail-checks.md` block harmful actions before any side effects occur — proven by end-to-end integration tests.

**Independent Test**: Attempt a refund exceeding $100 and verify the action is blocked with block_reason="dollar_cap", logged in the audit trail, and the response informs the customer it needs manual review.

### Integration Tests (write and run in parallel once US1 + US2 complete)

- [X] T056 [P] [US4] Write integration test: excess tool calls in one session are blocked after rate limit is reached with block_reason="rate_limit" in `tests/integration/test_tool_workflow.py`
- [X] T057 [P] [US4] Write integration test: refund amount exceeding TOOL_DOLLAR_CAP is blocked before execution with block_reason="dollar_cap" in `tests/integration/test_tool_workflow.py`
- [X] T058 [P] [US4] Write integration test: tool call with missing or invalid required params is rejected before execution with block_reason="invalid_params" in `tests/integration/test_tool_workflow.py`
- [X] T059 [P] [US4] Write integration test: issue_refund on a cancelled or pending order is blocked by check_refund_eligibility with block_reason="refund_ineligible" before any payment side effects occur in `tests/integration/test_tool_workflow.py`
- [X] T060 [P] [US4] Write integration test: issue_refund routes to approval queue and returns pending_approval status, is not executed immediately in `tests/integration/test_tool_workflow.py`
- [X] T061 [P] [US4] Write integration test: pending approval expires after APPROVAL_TIMEOUT_SECONDS, subsequent approve call returns 409 with status="expired" in `tests/integration/test_tool_workflow.py`
- [X] T062 [P] [US4] Write integration test: tool call using an unregistered tool name is rejected with block_reason="unknown_tool" before any execution in `tests/integration/test_tool_workflow.py`

**Checkpoint**: US4 verified — all nine guardrail checks proven end-to-end

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Validate the full feature against documented scenarios and confirm no regressions.

- [X] T063 [P] Validate all quickstart.md scenarios against the running server: order status (Section 1), ticket creation (Section 2), refund pending (Section 3), approve refund (Section 4), dollar cap block (Section 5)
- [X] T064 [P] Run full test suite to confirm existing RAG pipeline tests pass with no regressions: `pytest tests/ -v`
- [X] T065 Verify all 11 plan.md verification items pass (`make test-unit`, `make test-int`, autonomous read-only/low-risk execution, high-risk approval gating, rate limiting, dollar cap, invalid params, audit trail completeness, multi-tool sequencing, existing test non-regression)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **User Story Phases (3–6)**: All depend on Phase 2 completion
  - US1 (Phase 3), US2 (Phase 4), and US4 (Phase 6) can run in parallel once Phase 2 completes
  - US3 (Phase 5) depends on US1 completing (reuses order_status + create_ticket)
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Starts after Phase 2 — independent of US2, US3, US4
- **US2 (P1)**: Starts after Phase 2 — independent of US1 (separate tool + backend)
- **US3 (P2)**: Starts after US1 — reuses order_status and create_ticket from US1
- **US4 (P1)**: Starts after Phase 2 — integration tests exercise all tools (best run after US1 + US2)

### Guardrail Check Execution Order in execute_tool()

Per `design/tool-guardrail-checks.md`, checks run in this order (short-circuit on first failure):

1. `validate_agent_allowlist` — agent allow-list (T009)
2. `validate_params` — Pydantic schema (T010)
3. `validate_customer_id` — session customer_id match (T011)
4. `check_rate_limit` — call count per session (T015)
5. `check_idempotency` — duplicate key detection (T016)
6. `check_dollar_cap` — dollar threshold, financial tools only (T013)
7. `check_refund_eligibility` — order status policy, issue_refund only (T014)
8. `check_risk_level` — read-only/low/high routing (T012)
9. `check_requires_approval` — destructive action confirmation, high-risk only (T017)

### Within Each Phase

- TDD: tests MUST be written and FAIL before implementation tasks begin
- Mock backends before tool definitions (tool definitions call backends)
- Tool definitions before registry registration
- Registry before action_planner (planner reads registry)
- action_planner before action_executor
- Graph nodes before routing changes
- Routing before API schema updates

### Parallel Opportunities

- All [P]-marked setup tasks run in parallel
- All [P]-marked test-writing tasks run in parallel within their phase
- US1 mock backends (T029, T030) run in parallel
- US3 (Phase 5) and US4 (Phase 6) can run in parallel once US1 + US2 are complete
- All US4 integration tests (T056–T062) run in parallel

---

## Parallel Example: Phase 2 Foundational Tests

```bash
# Launch all four test stubs in parallel:
Task: T004 — Write failing tests for tool registry in tests/unit/test_registry.py
Task: T005 — Write failing tests for all 9 guardrail checks in tests/unit/test_guardrails.py
Task: T006 — Write failing tests for execute_tool() in tests/unit/test_executor.py
Task: T007 — Write failing tests for audit helpers in tests/unit/test_audit.py
```

## Parallel Example: User Story 1 Tests

```bash
# Launch all US1 test stubs in parallel:
Task: T023 — Mock order database tests in tests/unit/test_mock_backends.py
Task: T024 — Mock ticketing system tests in tests/unit/test_mock_backends.py
Task: T025 — order_status_lookup tests in tests/unit/test_order_status.py
Task: T026 — create_support_ticket tests in tests/unit/test_create_ticket.py
Task: T027 — action_planner tests in tests/unit/test_action_planner.py
Task: T028 — action_executor tests in tests/unit/test_action_executor.py
```

---

## Implementation Strategy

### MVP First (User Story 1 — Order Status Focus)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Foundational — all nine guardrail checks (T004–T022)
3. Complete Phase 3: US1 — order status lookup + ticket creation end-to-end (T023–T039)
4. **STOP and VALIDATE**: Run `pytest tests/unit/ tests/integration/test_tool_workflow.py -v` and validate quickstart Sections 1–2
5. Demo: `POST /query {"query_text": "What is the status of my order ORD-12345?"}` → agent returns real-time order data

### Incremental Delivery

1. Setup + Foundational → all nine guardrail checks working
2. US1 → autonomous low-risk actions (order lookup + ticket creation) → MVP demo
3. US2 → high-risk approval workflow (refund) → safety complete
4. US3 → multi-tool sequences working
5. US4 + Polish → all guardrails proven end-to-end, no regressions

### Parallel Team Strategy

With multiple developers (after Phase 2 completes):
- Developer A: US1 (order status + ticket creation + graph nodes)
- Developer B: US2 (refund tool + approval API)
- Developer C: US4 integration tests (guardrail end-to-end verification)

---

## Task Summary

| Phase | Count | Focus |
|---|---|---|
| Phase 1: Setup | 3 | Directory structure, stub files |
| Phase 2: Foundational | 19 | Registry, nine guardrail checks (T009–T017, one task each), executor, audit, state, config, observability |
| Phase 3: US1 (P1) 🎯 MVP | 17 | Order status + ticket creation + graph nodes + API schema |
| Phase 4: US2 (P1) | 11 | Refund tool + approval queue + approval API |
| Phase 5: US3 (P2) | 5 | Multi-tool sequencing + partial failure handling |
| Phase 6: US4 (P1) | 7 | Guardrail integration tests (one per check) |
| Phase 7: Polish | 3 | Quickstart validation + regression check |
| **Total** | **65** | |

**Parallel tasks**: 31 tasks marked [P]

**Guardrail checks** (from `design/tool-guardrail-checks.md`): 9 — each has a discrete test in T005 and a dedicated implementation task (T009–T017)

**Suggested MVP scope**: Phases 1–3 (39 tasks) delivering autonomous order status lookup and ticket creation
