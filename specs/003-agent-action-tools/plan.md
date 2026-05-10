# Implementation Plan: Agent Business Action Tools

**Branch**: `003-agent-action-tools` | **Date**: 2026-05-09 | **Spec**: `specs/003-agent-action-tools/spec.md`
**Input**: Feature specification from `specs/003-agent-action-tools/spec.md`

## Summary

Add wrapped, guardrailed business action tools to the LangGraph agent: order status lookup (read-only), support ticket creation (low-risk), and refund issuance (high-risk). Every tool call passes through a guardrail executor that validates parameters, enforces rate limits and dollar caps, routes high-risk actions to human approval, and logs an audit trail — agents never call tools directly. Simulated backend services stand in for production systems.

## Technical Context

| Dimension | Decision |
|---|---|
| **Language/Version** | Python 3.11+ |
| **Primary Dependencies** | `langgraph`, `langchain-openai`, `langchain-postgres`, `fastapi` (all existing) |
| **New Dependencies** | `pydantic` for tool input schemas (already transitive via `fastapi`/`pydantic-settings`) |
| **LLM** | Claude via `ChatAnthropic` / OpenAI via `ChatOpenAI` (existing) |
| **Storage** | PostgreSQL 16 + pgvector (existing); in-memory dicts for simulated backends |
| **Testing** | pytest (existing) |
| **Target Platform** | Linux server (local Docker Compose) |
| **Project Type** | Web service (FastAPI) |
| **Performance Goals** | < 5s per tool call (SC-001), < 30s end-to-end including tool execution |
| **Constraints** | Rate limit: configurable per session (default 10/min). Dollar cap: configurable (default $100). Approval timeout: configurable (default 300s). |
| **Scale/Scope** | POC, 3 tools, single-user, simulated backends |

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Research Check

| Principle | Status | Notes |
|---|---|---|
| **I. RAG-First** | PASS | Tools augment, not replace, the existing RAG pipeline (FR-014). The retrieval path remains the primary response mechanism. Tool execution happens alongside or after retrieval, not instead of it. |
| **II. Agentic Autonomy** | PASS | Core enabler. Agents autonomously decide when to use tools (Principle II mandates tool use for side-effect actions). The guardrail layer adds safety without removing autonomy — agents still choose *which* tool, guardrails gate *whether* it executes. |
| **III. Test-First** | PASS | TDD enforced. Every guardrail check, tool definition, and executor path gets a failing test before implementation. |
| **IV. Observability** | PASS | FR-009 requires logging every tool execution attempt (success, failure, blocked) with tool name, parameters, result, risk tier, timestamp, and session ID. Extends existing structlog infrastructure with new event types. |
| **V. Simplicity** | PASS | Three tools with simulated backends. No production integrations, no async approval queues, no distributed rate limiting. In-memory mocks, synchronous approval, per-session counters. |

### Post-Design Re-Check

| Principle | Status | Notes |
|---|---|---|
| **I. RAG-First** | PASS | Tool execution is a new graph path that branches from the existing retrieval pipeline. The `action_planner` node decides tool use based on retrieved context + query intent. Retrieval remains mandatory for all responses. |
| **II. Agentic Autonomy** | PASS | The LLM in `action_planner` autonomously selects tools and parameters. The guardrail executor validates but does not alter the agent's decision — it blocks unsafe calls and lets safe ones through. |
| **III. Test-First** | PASS | Unit tests for every guardrail check (schema validation, rate limiting, dollar caps, risk routing). Integration tests for end-to-end tool execution through the graph. |
| **IV. Observability** | PASS | New event types: `tool_call_attempt`, `tool_call_success`, `tool_call_blocked`, `tool_call_failed`, `approval_requested`, `approval_resolved`. Full audit trail with zero gaps (SC-003). |
| **V. Simplicity** | PASS | Flat module structure under `src/tools/`. No abstract factory, no plugin system, no dynamic tool loading. Three concrete tools, one registry dict, one guardrail pipeline function. |

## Phase 0: Research Decisions

| Decision | Resolution | Rationale |
|---|---|---|
| Tool wrapping pattern | Guardrail executor function that wraps every tool call | User requirement: "Do not let agents call tools directly. Wrap every tool." A single `execute_tool()` function validates, gates, and logs before delegating to the tool implementation. |
| LangGraph tool integration | Custom `action_planner` + `action_executor` nodes (not LangGraph ToolNode) | LangGraph's built-in `ToolNode` calls tools directly, bypassing guardrails. Custom nodes let us intercept every call. |
| Risk classification | Static per-tool metadata in tool definitions | Simplest approach for POC. Each tool declares its risk level at registration time. No dynamic risk assessment. |
| Rate limiting | In-memory per-session counter with sliding window | No Redis, no distributed state. Sufficient for single-user POC. |
| Human approval workflow | Synchronous in-memory queue | No async workers, no webhooks. The API exposes `/approvals` endpoints for a human reviewer. Action blocks until approved, rejected, or timed out. |
| Simulated backends | In-memory Python dicts with fake data | No external services. Deterministic for testing. |
| Graph topology change | Add `action_planner` → `action_executor` branch after `response_generator` | Tool actions are decided after the LLM has retrieval context. Keeps the existing retrieval pipeline intact. |

See `specs/003-agent-action-tools/research.md` for full research details.

## Phase 1: Data Model

See `specs/003-agent-action-tools/data-model.md` for full schema.

### State Schema Changes

New fields added to `SupportGraphState`:

| Field | Type | Purpose |
|---|---|---|
| `tool_calls` | `list[dict] \| None` | Planned tool calls from action_planner (name, params, risk) |
| `tool_results` | `Annotated[list[dict], _accumulate] \| None` | Executed tool results (outcome, audit entry) |
| `pending_approvals` | `list[dict] \| None` | High-risk actions awaiting human review |
| `action_taken` | `bool` | Whether any tool action was executed in this turn |

### Key Entities

| Entity | Fields | Purpose |
|---|---|---|
| **ToolDefinition** | name, description, input_schema, output_schema, risk_level, rate_limit, dollar_cap | Registered tool metadata |
| **ToolExecutionRecord** | tool_name, parameters, result, status (success/blocked/failed), risk_level, session_id, timestamp | Audit trail entry |
| **ApprovalRequest** | id, tool_name, parameters, requester_session, status (pending/approved/rejected/expired), created_at, expires_at, resolved_by, resolution_reason | Human approval queue entry |

### Database Changes

None. Tool execution records are logged via existing structlog infrastructure. Approval requests are held in memory (POC scope).

## Phase 1: Contracts

See `specs/003-agent-action-tools/contracts/api.md` for full contracts.

### New API Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/approvals` | List pending approval requests |
| POST | `/approvals/{id}/approve` | Approve a pending action |
| POST | `/approvals/{id}/reject` | Reject a pending action |

### POST /query Response Changes

New metadata fields: `tool_calls` (list of executed tools), `action_taken` (boolean), `pending_approvals` (list of actions awaiting review).

### Graph Node Signatures

```
action_planner(state)   → dict  (writes tool_calls — decides which tools to invoke)
action_executor(state)  → dict  (writes tool_results, pending_approvals — executes via guardrails)
```

### Tool Guardrail Pipeline

```
execute_tool(tool_name, params, session_id)
  → validate_tool_exists(tool_name)
  → validate_params(params, tool.input_schema)
  → check_rate_limit(session_id, tool_name)
  → check_dollar_cap(params, tool.dollar_cap)       # financial tools only
  → check_risk_level(tool.risk_level)
     → read-only / low: execute immediately
     → high: create ApprovalRequest, block until resolved
  → execute tool implementation
  → log ToolExecutionRecord
  → return result
```

## Project Structure

### Documentation (this feature)

```text
specs/003-agent-action-tools/
├── plan.md              # This file
├── research.md          # Phase 0 research decisions
├── data-model.md        # State schema + entity definitions
├── quickstart.md        # Getting started guide
├── contracts/
│   └── api.md           # API, tool, and node contracts
└── tasks.md             # (created by /speckit-tasks)
```

### Source Code (repository root)

```text
src/
├── agents/
│   ├── action_planner.py        # NEW: LLM-based tool selection + parameter extraction
│   ├── action_executor.py       # NEW: guardrail-wrapped tool execution node
│   ├── supervisor.py            # UNCHANGED
│   ├── security_check.py        # UNCHANGED
│   ├── retrieval_planner.py     # UNCHANGED
│   ├── multi_retriever.py       # UNCHANGED
│   ├── confidence_check.py      # UNCHANGED
│   ├── response_generator.py    # MODIFIED: detect tool-actionable queries, set flag for action path
│   ├── validate_response.py     # MODIFIED: include tool results in validation
│   ├── escalation_handler.py    # UNCHANGED
│   └── fallback.py              # UNCHANGED
│
├── tools/
│   ├── registry.py              # NEW: tool registry (dict of ToolDefinition)
│   ├── guardrails.py            # NEW: validation pipeline (schema, rate limit, dollar cap, risk)
│   ├── executor.py              # NEW: wrapped execute_tool() entry point
│   ├── audit.py                 # NEW: tool-specific audit logging helpers
│   ├── approval.py              # NEW: in-memory approval queue + resolution
│   └── definitions/
│       ├── order_status.py      # NEW: order status lookup (read-only)
│       ├── create_ticket.py     # NEW: support ticket creation (low-risk)
│       └── issue_refund.py      # NEW: refund issuance (high-risk)
│
├── tools/backends/
│   ├── mock_orders.py           # NEW: simulated order database
│   ├── mock_tickets.py          # NEW: simulated ticketing system
│   └── mock_payments.py         # NEW: simulated payment processor
│
├── graph/
│   ├── state.py                 # MODIFIED: new tool-related state fields
│   ├── workflow.py              # MODIFIED: add action_planner → action_executor path
│   └── routing.py               # MODIFIED: action routing logic
│
├── observability/
│   └── logger.py                # MODIFIED: new tool audit event helpers
│
├── api/
│   ├── main.py                  # MODIFIED: add /approvals endpoints
│   └── schemas.py               # MODIFIED: new response fields, approval schemas
│
├── db/
│   └── connection.py            # UNCHANGED
│
└── config.py                    # MODIFIED: new tool config params

tests/
├── unit/
│   ├── test_registry.py         # NEW: tool registration + discovery
│   ├── test_guardrails.py       # NEW: validation pipeline (schema, rate, dollar, risk)
│   ├── test_executor.py         # NEW: wrapped execution flow
│   ├── test_approval.py         # NEW: approval queue lifecycle
│   ├── test_audit.py            # NEW: audit logging
│   ├── test_order_status.py     # NEW: order lookup tool
│   ├── test_create_ticket.py    # NEW: ticket creation tool
│   ├── test_issue_refund.py     # NEW: refund tool
│   ├── test_action_planner.py   # NEW: tool selection node
│   ├── test_action_executor.py  # NEW: execution node
│   ├── test_mock_backends.py    # NEW: simulated services
│   └── ...                      # EXISTING tests unchanged
│
├── integration/
│   ├── test_tool_workflow.py    # NEW: end-to-end tool execution through graph
│   ├── test_approval_api.py     # NEW: approval endpoint integration
│   └── ...                      # EXISTING tests unchanged
│
└── evals/
    └── ...                      # EXISTING evals unchanged
```

**Structure Decision**: New `src/tools/` module for all tool-related code. Tool definitions, guardrails, and backends are co-located. Agent nodes for tool planning/execution live in `src/agents/` alongside existing nodes.

## LangGraph Flow (Updated)

```
START → supervisor → security_check → retrieval_planner → multi_retriever → confidence_check → response_generator
                   → fallback_handler → END                                                        ↓
                                      → escalation_handler → END                            [action_needed?]
                                                                                             ├─ No → validate_response → END
                                                                                             └─ Yes → action_planner → action_executor → validate_response → END
```

### New Node Descriptions

- **action_planner**: Receives the response context and determines if tool actions are needed. Uses structured LLM output to select tools from the registry and extract parameters. Writes `tool_calls` to state.
- **action_executor**: Iterates over `tool_calls` and executes each through `execute_tool()` (the guardrail wrapper). Never calls tool implementations directly. Writes `tool_results` and `pending_approvals` to state. For high-risk blocked actions, includes the pending approval info in the response.

### Why After response_generator (Not Before)

The action path branches *after* response_generator because:
1. The LLM needs retrieval context to make informed tool decisions (e.g., looking up which order to check)
2. Many queries need only a retrieval-based response — no tools at all
3. The response_generator can set an `action_needed` flag based on query intent + retrieved context
4. This keeps the existing retrieval pipeline completely intact (Principle I: RAG-First)

## Configuration Changes

New settings in `config.py`:

| Setting | Default | Description |
|---|---|---|
| `TOOL_RATE_LIMIT_PER_MINUTE` | 10 | Max tool executions per session per minute |
| `TOOL_DOLLAR_CAP` | 100.0 | Max dollar amount for financial actions |
| `APPROVAL_TIMEOUT_SECONDS` | 300 | Seconds before a pending approval expires |
| `TOOL_EXECUTION_ENABLED` | True | Global kill switch for tool execution |

## Implementation Sequence (TDD)

Each step: write test (RED) → confirm fail → implement (GREEN).

### Phase 1: Tool Infrastructure

1. Define `ToolDefinition` dataclass + tool registry → `test_registry.py` → `tools/registry.py`
2. Implement parameter schema validation guardrail → `test_guardrails.py` → `tools/guardrails.py`
3. Implement rate limiting guardrail → `test_guardrails.py` → `tools/guardrails.py`
4. Implement dollar cap guardrail → `test_guardrails.py` → `tools/guardrails.py`
5. Implement risk-level routing guardrail → `test_guardrails.py` → `tools/guardrails.py`
6. Implement `execute_tool()` wrapper → `test_executor.py` → `tools/executor.py`
7. Implement audit logging helpers → `test_audit.py` → `tools/audit.py`

### Phase 2: Mock Backends & Tool Definitions

8. Implement mock order database → `test_mock_backends.py` → `tools/backends/mock_orders.py`
9. Implement mock ticketing system → `test_mock_backends.py` → `tools/backends/mock_tickets.py`
10. Implement mock payment processor → `test_mock_backends.py` → `tools/backends/mock_payments.py`
11. Define order_status_lookup tool → `test_order_status.py` → `tools/definitions/order_status.py`
12. Define create_support_ticket tool → `test_create_ticket.py` → `tools/definitions/create_ticket.py`
13. Define issue_refund tool → `test_issue_refund.py` → `tools/definitions/issue_refund.py`

### Phase 3: Approval Workflow (User Story 2)

14. Implement approval queue → `test_approval.py` → `tools/approval.py`
15. Add approval API endpoints → `test_approval_api.py` → `api/main.py`
16. Add approval Pydantic schemas → `api/schemas.py`

### Phase 4: Graph Nodes (User Story 1 + 3)

17. Extend state schema with tool fields → `test_state.py` → `graph/state.py`
18. Add new config parameters → `config.py`
19. Add new observability event helpers → `test_logger.py` → `observability/logger.py`
20. Implement action_planner node → `test_action_planner.py` → `agents/action_planner.py`
21. Implement action_executor node → `test_action_executor.py` → `agents/action_executor.py`
22. Modify response_generator to detect tool-actionable queries → update existing tests
23. Add action routing to workflow → `test_tool_workflow.py` → `graph/workflow.py`, `graph/routing.py`
24. Update validate_response for tool results → existing tests
25. Update API response schemas → `api/schemas.py`

### Phase 5: Safety Guardrails End-to-End (User Story 4)

26. Integration test: rate limit blocks excess calls → `test_tool_workflow.py`
27. Integration test: dollar cap blocks over-limit refunds → `test_tool_workflow.py`
28. Integration test: invalid params rejected before execution → `test_tool_workflow.py`
29. Integration test: high-risk action routes to approval → `test_tool_workflow.py`
30. Integration test: approval timeout expires pending action → `test_tool_workflow.py`

## Conflict Resolutions

| Conflict | Resolution |
|---|---|
| LangGraph ToolNode calls tools directly | Custom action_executor node wraps all calls through guardrail pipeline. User explicitly required: "Do not let agents call tools directly. Wrap every tool." |
| Tools could bypass RAG pipeline | Action path branches *after* retrieval, ensuring RAG-first principle is maintained. Tools augment responses, never replace retrieval. |
| Approval workflow complexity vs POC simplicity | Synchronous in-memory queue. No async workers, no persistent storage, no webhooks. Minimal viable approval flow. |

## Verification

1. `make test-unit` — All unit tests pass (mocked dependencies)
2. `make test-int` — Integration tests pass including tool workflow
3. Read-only tool (order_status) executes autonomously without approval
4. Low-risk tool (create_ticket) executes autonomously without approval
5. High-risk tool (issue_refund) routes to approval queue, blocks until resolved
6. Rate limit blocks tool calls exceeding configured threshold
7. Dollar cap blocks refunds exceeding configured limit
8. Invalid parameters rejected before any tool execution
9. Every tool execution attempt logged with full audit trail (SC-003)
10. Multi-tool sequences execute in order, later tools can reference earlier results
11. Existing RAG pipeline tests continue to pass (no regressions)
