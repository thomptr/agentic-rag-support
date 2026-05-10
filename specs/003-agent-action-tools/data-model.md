# Data Model: Agent Business Action Tools

**Feature**: 003-agent-action-tools | **Date**: 2026-05-09

## State Schema Changes

### New Fields on `SupportGraphState`

```python
class SupportGraphState(TypedDict):
    # ... existing fields from 001 + 002 ...

    # Tool execution state (003)
    tool_calls: list[dict] | None          # Planned tool invocations from action_planner
    tool_results: Annotated[list[dict], _accumulate] | None  # Execution outcomes
    pending_approvals: list[dict] | None   # High-risk actions awaiting review
    action_taken: bool                     # Whether any tool was executed this turn
```

### Field Schemas

#### `tool_calls` (written by `action_planner`)

```python
{
    "tool_name": str,           # Must match a registered tool name
    "parameters": dict,         # Must validate against tool's input_schema
    "risk_level": str,          # "read-only" | "low" | "high" (from registry)
    "reason": str               # LLM's rationale for selecting this tool
}
```

#### `tool_results` (written by `action_executor`)

```python
{
    "tool_name": str,
    "parameters": dict,         # Echo of what was passed
    "status": str,              # "success" | "blocked" | "failed" | "pending_approval"
    "result": dict | None,      # Tool output (if success)
    "error": str | None,        # Error message (if blocked or failed)
    "block_reason": str | None, # Why blocked (rate_limit | dollar_cap | invalid_params | unknown_tool)
    "approval_id": str | None,  # Reference to ApprovalRequest (if pending_approval)
    "timestamp": str            # ISO 8601
}
```

#### `pending_approvals` (written by `action_executor`)

```python
{
    "id": str,                  # UUID
    "tool_name": str,
    "parameters": dict,
    "status": str,              # "pending" | "approved" | "rejected" | "expired"
    "created_at": str,          # ISO 8601
    "expires_at": str           # ISO 8601
}
```

## Entity Definitions

### ToolDefinition

Registered at startup. Immutable during execution.

```python
@dataclass
class ToolDefinition:
    name: str                       # Unique tool identifier (e.g., "order_status_lookup")
    description: str                # Human-readable description for LLM tool selection
    input_schema: type[BaseModel]   # Pydantic model for parameter validation
    output_schema: type[BaseModel]  # Pydantic model for result structure
    risk_level: str                 # "read-only" | "low" | "high"
    execute_fn: Callable            # The actual tool implementation function
    rate_limit: int | None          # Max calls per minute (None = use global default)
    dollar_cap: float | None        # Max dollar amount per call (None = no cap / non-financial)
```

### ToolExecutionRecord (Audit)

Emitted as a structured log event. Not stored in a database table.

```python
{
    "event_type": str,          # "tool_call_attempt" | "tool_call_success" | "tool_call_blocked" | "tool_call_failed"
    "tool_name": str,
    "parameters": dict,
    "risk_level": str,
    "session_id": str,
    "status": str,              # "success" | "blocked" | "failed" | "pending_approval"
    "result": dict | None,
    "error": str | None,
    "block_reason": str | None,
    "timestamp": str            # ISO 8601
}
```

### ApprovalRequest

In-memory object managed by the approval module.

```python
@dataclass
class ApprovalRequest:
    id: str                     # UUID
    tool_name: str
    parameters: dict
    requester_session: str      # Session ID that triggered the action
    status: str                 # "pending" | "approved" | "rejected" | "expired"
    created_at: datetime
    expires_at: datetime
    resolved_by: str | None     # Reviewer identifier (if approved/rejected)
    resolution_reason: str | None  # Why approved/rejected
```

## Tool Input/Output Schemas

### order_status_lookup

**Risk level**: read-only

```python
class OrderStatusInput(BaseModel):
    order_id: str               # e.g., "ORD-12345"

class OrderStatusOutput(BaseModel):
    order_id: str
    status: str                 # "pending" | "shipped" | "delivered" | "cancelled"
    created_at: str
    updated_at: str
    items: list[dict]           # [{"name": str, "quantity": int, "price": float}]
    total: float
    tracking_number: str | None
```

### create_support_ticket

**Risk level**: low

```python
class CreateTicketInput(BaseModel):
    subject: str                # Ticket subject line
    description: str            # Detailed description
    priority: str = "medium"    # "low" | "medium" | "high"
    category: str = "general"   # "billing" | "technical" | "account" | "general"

class CreateTicketOutput(BaseModel):
    ticket_id: str              # e.g., "TKT-001"
    status: str                 # "open"
    created_at: str
```

### issue_refund

**Risk level**: high

```python
class IssueRefundInput(BaseModel):
    order_id: str               # Order to refund
    amount: float               # Refund amount (must be > 0)
    reason: str                 # Reason for refund

class IssueRefundOutput(BaseModel):
    refund_id: str              # e.g., "REF-001"
    order_id: str
    amount: float
    status: str                 # "processed" (after approval)
    processed_at: str
```

## Mock Backend Data

### Orders (mock_orders.py)

| order_id | status | total | items |
|---|---|---|---|
| ORD-12345 | shipped | 79.99 | Widget A (x2), Widget B (x1) |
| ORD-12346 | delivered | 149.50 | Premium Kit (x1) |
| ORD-12347 | pending | 29.99 | Basic Plan (x1) |
| ORD-12348 | cancelled | 199.00 | Enterprise License (x1) |
| ORD-12349 | shipped | 54.75 | Adapter (x3), Cable (x1) |

### Payments (mock_payments.py)

| payment_id | order_id | amount | status |
|---|---|---|---|
| PAY-001 | ORD-12345 | 79.99 | completed |
| PAY-002 | ORD-12346 | 149.50 | completed |
| PAY-003 | ORD-12347 | 29.99 | completed |

## Database Changes

None. All tool execution state is in-memory (graph state + approval queue). Audit trail uses existing structlog infrastructure.

## Observability Event Types (New)

| Event Type | When Emitted | Key Fields |
|---|---|---|
| `tool_call_attempt` | Before guardrail checks | tool_name, parameters, risk_level, session_id |
| `tool_call_success` | After successful execution | tool_name, parameters, result, duration_ms |
| `tool_call_blocked` | When guardrail blocks execution | tool_name, parameters, block_reason |
| `tool_call_failed` | When tool execution errors | tool_name, parameters, error |
| `approval_requested` | When high-risk action queued | approval_id, tool_name, parameters, expires_at |
| `approval_resolved` | When approval approved/rejected/expired | approval_id, status, resolved_by |
