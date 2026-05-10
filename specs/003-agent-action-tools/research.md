# Research: Agent Business Action Tools

**Feature**: 003-agent-action-tools | **Date**: 2026-05-09

## Research Task 1: Tool Wrapping Pattern for LangGraph

**Question**: How should we wrap every tool call so agents never invoke tools directly?

### Findings

**LangGraph's built-in ToolNode** (`langgraph.prebuilt.ToolNode`) is designed for direct tool execution: the LLM produces `tool_calls` in its response, and `ToolNode` dispatches them immediately. This bypasses any guardrail layer — there is no hook point between "LLM decides to call tool" and "tool executes."

**Alternative approaches evaluated**:

| Approach | Description | Pros | Cons |
|---|---|---|---|
| **A. Custom executor node** *(chosen)* | Separate `action_planner` (LLM selects tools) and `action_executor` (guardrails + execute) | Full control over every call. Clear separation of intent vs execution. Guardrails run between planning and execution. | Two nodes instead of one. Slightly more graph complexity. |
| B. Monkey-patch ToolNode | Subclass `ToolNode` and override `_func_invoke` | Reuses LangGraph plumbing. | Fragile — depends on internal API. Coupling to LangGraph internals. |
| C. Decorator on tool functions | `@guardrailed` decorator wrapping each tool function | Simple per-tool application. | Guardrails are scattered across tool files. No central enforcement point. A new tool could forget the decorator. |
| D. LangGraph middleware/hooks | Use LangGraph's `on_tool_start` callback hooks | Non-invasive. | Callbacks can observe but not block execution in current LangGraph versions. Rate limiting and approval require blocking. |

**Decision**: **Option A — Custom executor node**

**Rationale**: The user explicitly requires "Do not let agents call tools directly. Wrap every tool." A custom `action_executor` node is the only approach that guarantees central enforcement. Every tool call flows through a single `execute_tool()` function that validates, gates, and logs before delegating. No tool can be invoked outside this path because tool implementation functions are not exposed as LangGraph tools — they are internal functions called only by the executor.

---

## Research Task 2: Risk Classification Strategy

**Question**: How should tools be classified into risk tiers, and where does classification live?

### Findings

The spec defines three tiers (FR-002):
- **read-only**: No side effects (e.g., order status lookup)
- **low**: Reversible side effects (e.g., creating a support ticket)
- **high**: Irreversible or financially significant (e.g., issuing a refund)

**Approaches evaluated**:

| Approach | Description | Trade-off |
|---|---|---|
| **A. Static per-tool metadata** *(chosen)* | Risk level declared in the `ToolDefinition` at registration time | Simple, explicit, auditable. Cannot adapt to parameters. |
| B. Dynamic per-call assessment | LLM or rule engine evaluates risk per invocation based on parameters | Flexible (e.g., small refund = low, large refund = high). Complex, requires an extra LLM call or rule engine. |
| C. Hybrid: static default + parameter overrides | Base risk level on tool, with parameter-based escalation rules | Best of both, but more complex than needed for POC. |

**Decision**: **Option A — Static per-tool metadata**

**Rationale**: POC scope (Principle V). Three tools, each with a clear risk level. Dynamic assessment adds complexity with no POC value — the refund tool is always high-risk regardless of amount (the dollar cap guardrail handles amount limits separately). Static classification is auditable: you can read the tool registry and see every tool's risk level without running code.

---

## Research Task 3: Rate Limiting Implementation

**Question**: What rate limiting approach fits a single-user POC?

### Findings

| Approach | Description | Trade-off |
|---|---|---|
| **A. In-memory sliding window** *(chosen)* | Dict mapping `(session_id, tool_name) → list[timestamp]`. Count calls in last 60s. | Zero dependencies. Sufficient for POC. Resets on restart. |
| B. Token bucket (in-memory) | Classic token bucket per session per tool | More sophisticated, handles bursts better. Overkill for POC. |
| C. Redis-backed rate limiter | Distributed rate limiting with Redis | Production-grade. Requires Redis. Violates Principle V. |

**Decision**: **Option A — In-memory sliding window**

**Rationale**: The POC is single-user, single-process. An in-memory dict with timestamp lists is the simplest correct implementation. The sliding window naturally handles the "per minute" requirement from FR-007. No new dependencies.

---

## Research Task 4: Human Approval Workflow

**Question**: How should the human approval workflow work for high-risk actions?

### Findings

The spec requires high-risk actions to block until a human approves or rejects (FR-005), with a configurable timeout for expiration (FR-012).

| Approach | Description | Trade-off |
|---|---|---|
| **A. Synchronous in-memory queue** *(chosen)* | In-memory dict of `ApprovalRequest` objects. API endpoints for list/approve/reject. `execute_tool()` creates request and returns "pending" status. | Simple. No async. No persistence. Approval state lost on restart. |
| B. Database-backed queue | Store approvals in PostgreSQL. Poll for resolution. | Persistent. Survives restarts. Adds DB migration, more complexity. |
| C. Webhook/callback pattern | Send approval request to external system, wait for callback. | Production-grade. Requires external system. Way beyond POC scope. |
| D. LangGraph interrupt | Use LangGraph's `interrupt()` to pause graph execution at the approval point. | Native LangGraph pattern. Requires checkpointer for state persistence. More complex graph lifecycle. |

**Decision**: **Option A — Synchronous in-memory queue**

**Rationale**: POC scope. The approval queue is a dict. The executor creates an `ApprovalRequest`, returns a "pending_approval" status in the tool result, and the response includes the pending approval info so the customer knows their request is being reviewed. A separate API call (POST `/approvals/{id}/approve`) resolves the approval. For the POC, we don't need to block the graph execution waiting for approval — instead the tool result simply indicates "pending human review" and the response to the customer says as much. A follow-up query or API call triggers the actual execution after approval.

---

## Research Task 5: Graph Topology — Where to Place Tool Execution

**Question**: Where in the existing LangGraph flow should tool execution happen?

### Findings

| Placement | Description | Trade-off |
|---|---|---|
| A. Before retrieval | Supervisor decides tools before any retrieval | Breaks RAG-first principle. Agent has no context to make good tool decisions. |
| B. Parallel to retrieval | Separate branch from supervisor: one for retrieval, one for tools | Complex graph. Tools and retrieval can't inform each other. |
| **C. After response_generator** *(chosen)* | Response generator flags if tools are needed. Action nodes branch after. | RAG-first preserved. LLM has full retrieval context for tool decisions. Simple conditional branch. |
| D. Inside response_generator | Single node does both generation and tool execution | Violates single responsibility. Hard to test guardrails independently. |

**Decision**: **Option C — After response_generator**

**Rationale**: The LLM needs retrieval context to make informed tool decisions (e.g., "Which order should I look up? The customer mentioned order #12345 in the conversation and the KB article says order lookups require an order ID."). Placing tools after retrieval + response generation ensures the agent has maximum context. The response_generator sets an `action_needed` flag, and a conditional edge routes to `action_planner` → `action_executor` → `validate_response`, or directly to `validate_response` if no action is needed.

---

## Research Task 6: Simulated Backend Design

**Question**: How should the mock backends be structured for testability?

### Findings

Each mock backend needs:
1. Deterministic data for testing (known orders, known customers)
2. Configurable failure modes (service unavailable, not found)
3. Simple Python interface (function call, not HTTP)

**Decision**: Each mock backend is a Python module with a dict of fake data and functions that operate on it. Functions accept a `fail_mode` parameter for testing error paths.

**Mock data**:
- **Orders**: 5 orders with known IDs, statuses, amounts, dates
- **Tickets**: Counter-based ID generation, in-memory list
- **Payments**: 3 payment records linked to orders, refund creates a new record

This mirrors real service interfaces closely enough that swapping to real HTTP clients later is straightforward — replace the mock function with an HTTP call, keep the same signature.

---

## Summary of Decisions

| # | Decision | Resolution | Rationale |
|---|---|---|---|
| 1 | Tool wrapping pattern | Custom executor node (`action_planner` + `action_executor`) | Central guardrail enforcement. User requirement. |
| 2 | Risk classification | Static per-tool metadata in `ToolDefinition` | Simple, explicit, auditable. POC scope. |
| 3 | Rate limiting | In-memory sliding window counter | Zero dependencies. Single-user POC. |
| 4 | Human approval | Synchronous in-memory queue with API endpoints | Minimal viable workflow. POC scope. |
| 5 | Graph placement | After response_generator (conditional branch) | RAG-first preserved. LLM has full context. |
| 6 | Simulated backends | In-memory dicts with deterministic test data | Testable, no external deps. |
