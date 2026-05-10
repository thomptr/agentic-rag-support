# Data Model: Frontend Chat UI, Agent Observability & Demo Console

**Feature**: `004-frontend-chat-observability`
**Date**: 2026-05-09

## Frontend State (Streamlit session_state)

All frontend state lives in `st.session_state`. No database tables, no persistent storage.

### Session State Keys

| Key | Type | Default | Description |
|---|---|---|---|
| `messages` | `list[ChatMessage]` | `[]` | Ordered conversation history |
| `selected_customer` | `str` | `"cust-003"` | Active customer profile ID |
| `selected_scenario` | `str \| None` | `None` | Selected preset scenario ID, or None for freeform |
| `guardrails_enabled` | `bool` | `True` | Whether tool execution guardrails are active |
| `selected_model` | `str` | `"gpt-4o-mini"` | LLM model for query processing |
| `pending_approvals` | `list[dict]` | `[]` | Approval items awaiting human action |
| `last_trace` | `TraceData \| None` | `None` | Full trace from most recent assistant response |
| `session_id` | `str` | Generated UUID | Unique ID for this browser session |

## Entity Definitions

### ChatMessage

A single message in the conversation.

| Field | Type | Required | Description |
|---|---|---|---|
| `role` | `str` | Yes | `"user"` or `"assistant"` |
| `content` | `str` | Yes | Message text content |
| `timestamp` | `str` | Yes | ISO 8601 timestamp |
| `trace` | `TraceData \| None` | No | Observability data (assistant messages only) |

### TraceData

Full observability payload attached to each assistant response. Derived from the backend `QueryResponse`.

| Field | Type | Required | Description |
|---|---|---|---|
| `query_id` | `str` | Yes | Unique query identifier |
| `agent` | `str` | Yes | Agent that handled the query (e.g., `"billing_agent"`) |
| `routing_rationale` | `str \| None` | No | Supervisor's reasoning for routing decision |
| `classified_domain` | `str \| None` | No | Primary domain classification |
| `classified_domains` | `list[str]` | Yes | All relevant domains |
| `citations` | `list[Citation]` | Yes | Retrieved documents with relevance scores |
| `tool_calls` | `list[ToolCall]` | Yes | Tool execution results |
| `pending_approvals` | `list[Approval]` | Yes | Actions awaiting human review |
| `metadata` | `QueryMetrics` | Yes | Timing and count metrics |
| `raw_response` | `dict` | Yes | Full serialized QueryResponse |

### Citation (from backend CitationResponse)

| Field | Type | Description |
|---|---|---|
| `content` | `str` | Document chunk text |
| `domain` | `str` | Knowledge domain (billing, technical, account) |
| `source` | `str` | Source document identifier |
| `score` | `float` | Relevance score (0.0 - 1.0) |

### ToolCall (from backend ToolCallResult)

| Field | Type | Description |
|---|---|---|
| `tool_name` | `str` | Name of the tool invoked |
| `status` | `str` | Execution status: `"success"`, `"blocked"`, `"failed"`, `"pending_approval"` |
| `result` | `dict \| None` | Tool execution result data |
| `error` | `str \| None` | Error message if failed |
| `block_reason` | `str \| None` | Reason for guardrail block |
| `approval_id` | `str \| None` | ID if pending human approval |

### Approval (from backend ApprovalItem)

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique approval request ID |
| `tool_name` | `str` | Tool awaiting approval |
| `parameters` | `dict` | Tool parameters for review |
| `status` | `str` | `"pending"`, `"approved"`, `"rejected"`, `"expired"` |
| `created_at` | `str` | ISO 8601 creation timestamp |
| `expires_at` | `str` | ISO 8601 expiration timestamp |

### QueryMetrics (from backend QueryMetadata)

| Field | Type | Description |
|---|---|---|
| `run_id` | `str` | LangGraph run identifier |
| `total_latency_ms` | `float` | End-to-end processing time |
| `llm_calls` | `int` | Number of LLM invocations |
| `retrieval_calls` | `int` | Number of retrieval operations |
| `retrieval_attempts` | `int` | Total retrieval attempts (including retries) |
| `documents_retrieved` | `int` | Raw documents retrieved |
| `documents_after_dedup` | `int` | Documents after deduplication |
| `retrieval_confidence` | `float \| None` | Confidence score for retrieval quality |

### PresetScenario

A predefined demo query.

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique scenario identifier (e.g., `"billing-update"`) |
| `category` | `str` | Category: `"billing"`, `"technical"`, or `"account"` |
| `title` | `str` | Short display title |
| `query_text` | `str` | The preset question text |
| `description` | `str` | Brief description for the scenario selector |

### CustomerProfile

A selectable customer identity for demo context.

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique customer ID (e.g., `"cust-001"`) |
| `name` | `str` | Display name |
| `description` | `str` | Brief description of customer type |

## Backend Schema Changes

### QueryRequest (modified)

Two new optional fields:

```python
class QueryRequest(BaseModel):
    query_text: str = Field(..., min_length=1, max_length=10000)
    session_id: str | None = None
    guardrails_enabled: bool | None = None    # NEW
    model_override: str | None = None          # NEW
```

### No Changes to Response Schemas

`QueryResponse`, `CitationResponse`, `QueryMetadata`, `ToolCallResult`, `ApprovalItem` — all remain unchanged. The frontend consumes these as-is.

## State Flow Diagram

```
Browser Session Start
  |
  v
Initialize st.session_state:
  messages=[], selected_customer="cust-003",
  guardrails_enabled=True, selected_model="gpt-4o-mini"
  |
  v
User selects customer / scenario / model (sidebar)
  -> Updates st.session_state
  |
  v
User types or selects preset query
  -> Append ChatMessage(role="user") to messages
  -> POST /query with session_id, guardrails_enabled, model_override
  -> Receive QueryResponse
  -> Build TraceData from response
  -> Append ChatMessage(role="assistant", trace=TraceData) to messages
  -> Set last_trace = TraceData
  -> Update pending_approvals from response
  |
  v
Observability tabs render from last_trace
  |
  v
Reset button -> Clear messages, last_trace, pending_approvals
```
