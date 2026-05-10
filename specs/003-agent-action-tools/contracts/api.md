# Contracts: Agent Business Action Tools

**Feature**: 003-agent-action-tools | **Date**: 2026-05-09

## Tool Registry Interface

### `get_registry() → dict[str, ToolDefinition]`

Returns the complete tool registry. Called by `action_planner` to discover available tools and by `action_executor` to look up tool metadata.

### `get_tool(name: str) → ToolDefinition | None`

Returns a single tool definition by name, or `None` if not registered.

### `get_tool_descriptions() → list[dict]`

Returns simplified tool metadata for LLM consumption (name, description, input schema as JSON schema). Used by `action_planner` to construct the tool selection prompt.

```python
[
    {
        "name": "order_status_lookup",
        "description": "Look up the current status of a customer order by order ID.",
        "parameters": { ... JSON Schema from input_schema ... },
        "risk_level": "read-only"
    },
    ...
]
```

---

## Guardrail Pipeline Interface

### `execute_tool(tool_name: str, parameters: dict, session_id: str) → ToolResult`

The single entry point for all tool execution. Agents never call tool implementations directly.

**Pipeline steps** (in order, short-circuits on first failure):

1. `validate_tool_exists(tool_name)` → raises `UnknownToolError`
2. `validate_params(parameters, tool.input_schema)` → raises `InvalidParamsError`
3. `check_rate_limit(session_id, tool_name)` → raises `RateLimitError`
4. `check_dollar_cap(parameters, tool.dollar_cap)` → raises `DollarCapError` (financial tools only)
5. `check_risk_level(tool.risk_level)`:
   - `read-only` / `low` → proceed to execution
   - `high` → create `ApprovalRequest`, return `pending_approval` status
6. Execute `tool.execute_fn(validated_params)` → return result
7. Log `ToolExecutionRecord` (success, blocked, or failed)

**Return type**:

```python
@dataclass
class ToolResult:
    tool_name: str
    status: str              # "success" | "blocked" | "failed" | "pending_approval"
    result: dict | None      # Tool output (if success)
    error: str | None        # Error message (if blocked or failed)
    block_reason: str | None # "rate_limit" | "dollar_cap" | "invalid_params" | "unknown_tool"
    approval_id: str | None  # ApprovalRequest ID (if pending_approval)
```

**Error behavior**: Guardrail violations do not raise exceptions to the caller. They return a `ToolResult` with `status="blocked"` and the appropriate `block_reason`. Only unexpected errors (bugs in tool code) propagate as `status="failed"`.

---

## Approval API Endpoints

### `GET /approvals`

List all pending approval requests.

**Response** `200 OK`:
```json
{
    "approvals": [
        {
            "id": "uuid",
            "tool_name": "issue_refund",
            "parameters": {"order_id": "ORD-12345", "amount": 79.99, "reason": "Defective product"},
            "status": "pending",
            "requester_session": "session-abc",
            "created_at": "2026-05-09T10:30:00Z",
            "expires_at": "2026-05-09T10:35:00Z"
        }
    ]
}
```

### `POST /approvals/{id}/approve`

Approve a pending action.

**Request body**:
```json
{
    "reviewer": "admin@example.com",
    "reason": "Customer verified, refund authorized"
}
```

**Response** `200 OK`:
```json
{
    "id": "uuid",
    "status": "approved",
    "tool_name": "issue_refund",
    "result": { ... tool execution output ... }
}
```

**Error responses**:
- `404`: Approval request not found
- `409`: Already resolved (approved, rejected, or expired)

### `POST /approvals/{id}/reject`

Reject a pending action.

**Request body**:
```json
{
    "reviewer": "admin@example.com",
    "reason": "Amount exceeds policy for this customer tier"
}
```

**Response** `200 OK`:
```json
{
    "id": "uuid",
    "status": "rejected",
    "reason": "Amount exceeds policy for this customer tier"
}
```

---

## POST /query Response Changes

Existing response schema extended with tool metadata:

```json
{
    "response_text": "...",
    "citations": [...],
    "agent": "support",
    "routing_rationale": "...",
    "classified_domains": ["billing"],
    "retrieval_attempts": 1,
    "documents_retrieved": 5,
    "documents_after_dedup": 5,
    "retrieval_confidence": 0.85,

    "tool_calls": [
        {
            "tool_name": "order_status_lookup",
            "status": "success",
            "result": {"order_id": "ORD-12345", "status": "shipped", ...}
        }
    ],
    "action_taken": true,
    "pending_approvals": []
}
```

When a high-risk action is pending:

```json
{
    "response_text": "I've submitted your refund request for review. A team member will approve it shortly. Your request ID is ...",
    "tool_calls": [
        {
            "tool_name": "issue_refund",
            "status": "pending_approval",
            "approval_id": "uuid"
        }
    ],
    "action_taken": false,
    "pending_approvals": [
        {
            "id": "uuid",
            "tool_name": "issue_refund",
            "parameters": {"order_id": "ORD-12345", "amount": 79.99, "reason": "..."},
            "status": "pending",
            "expires_at": "2026-05-09T10:35:00Z"
        }
    ]
}
```

---

## Graph Node Signatures

### `action_planner(state: SupportGraphState) → dict`

**Reads**: `query_text`, `response_text`, `merged_results`, `classified_domains`
**Writes**: `tool_calls`, `log_events`

Uses structured LLM output to decide which tools (if any) to call, based on:
- The customer's query
- The retrieved context
- The response already generated
- Available tools from the registry

**LLM structured output schema**:
```python
class ToolCallPlan(BaseModel):
    action_needed: bool
    tool_calls: list[PlannedToolCall]

class PlannedToolCall(BaseModel):
    tool_name: str
    parameters: dict
    reason: str
```

If `action_needed` is `False`, writes empty `tool_calls` and the routing function sends to `validate_response`.

### `action_executor(state: SupportGraphState) → dict`

**Reads**: `tool_calls`, `session_id`
**Writes**: `tool_results`, `pending_approvals`, `action_taken`, `response_text` (appends tool result info), `log_events`

Iterates over `tool_calls` and executes each via `execute_tool()`. Accumulates results. If any tool returns `pending_approval`, includes the approval info. Appends tool output summaries to `response_text` so the customer sees the results.

---

## Tool Implementation Signatures

Each tool is a plain Python function. Not a LangGraph tool. Not decorated. Called only by the executor.

```python
# tools/definitions/order_status.py
def order_status_lookup(params: OrderStatusInput) -> OrderStatusOutput:
    """Look up order status from the mock order database."""

# tools/definitions/create_ticket.py
def create_support_ticket(params: CreateTicketInput) -> CreateTicketOutput:
    """Create a support ticket in the mock ticketing system."""

# tools/definitions/issue_refund.py
def issue_refund(params: IssueRefundInput) -> IssueRefundOutput:
    """Issue a refund through the mock payment processor."""
```

---

## Observability Contract

Every tool execution emits structured log events via `structlog`. Event types and their required fields:

| Event | Required Fields |
|---|---|
| `tool_call_attempt` | `tool_name`, `parameters`, `risk_level`, `session_id` |
| `tool_call_success` | `tool_name`, `parameters`, `result`, `duration_ms`, `session_id` |
| `tool_call_blocked` | `tool_name`, `parameters`, `block_reason`, `session_id` |
| `tool_call_failed` | `tool_name`, `parameters`, `error`, `session_id` |
| `approval_requested` | `approval_id`, `tool_name`, `parameters`, `expires_at`, `session_id` |
| `approval_resolved` | `approval_id`, `status`, `resolved_by`, `resolution_reason` |

All events include `timestamp` (ISO 8601) automatically via structlog's `TimeStamper`.
