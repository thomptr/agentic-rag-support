# API Contracts: Frontend Chat UI, Agent Observability & Demo Console

**Feature**: `004-frontend-chat-observability`
**Date**: 2026-05-09

## Modified Endpoints

### POST /query

**Change**: Accept two new optional fields in the request body.

#### Request (modified)

```json
{
  "query_text": "How do I update my billing information?",
  "session_id": "cust-001",
  "guardrails_enabled": true,
  "model_override": "gpt-4o-mini"
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `query_text` | `string` | Yes | — | The support question (1-10000 chars) |
| `session_id` | `string \| null` | No | `null` | Session identifier (maps to customer profile in frontend) |
| `guardrails_enabled` | `boolean \| null` | No | `null` | Override tool execution guardrails. `null` = use server default. |
| `model_override` | `string \| null` | No | `null` | Override LLM model. `null` = use server default. Accepted values: `"gpt-4o-mini"`, `"gpt-4o"`, `"claude-sonnet-4-6"`. |

#### Response (unchanged)

```json
{
  "query_id": "uuid",
  "response_text": "You can update your billing information by...",
  "agent": "billing_agent",
  "routing_rationale": "Query relates to billing account management",
  "citations": [
    {
      "content": "To update billing info, navigate to...",
      "domain": "billing",
      "source": "billing-faq.md",
      "score": 0.87
    }
  ],
  "metadata": {
    "classified_domain": "billing",
    "classified_domains": ["billing"],
    "run_id": "uuid",
    "total_latency_ms": 2340.5,
    "llm_calls": 3,
    "retrieval_calls": 1,
    "retrieval_attempts": 1,
    "documents_retrieved": 5,
    "documents_after_dedup": 4,
    "retrieval_confidence": 0.82
  },
  "tool_calls": [],
  "action_taken": false,
  "pending_approvals": []
}
```

The response schema is unchanged from Feature 003. All fields documented in `src/api/schemas.py`.

## Existing Endpoints Consumed (unchanged)

### GET /approvals

**Frontend usage**: Poll for pending approval items to display in the UI.

#### Response

```json
{
  "approvals": [
    {
      "id": "uuid",
      "tool_name": "issue_refund",
      "parameters": {"order_id": "ORD-001", "amount": 49.99, "reason": "duplicate charge"},
      "status": "pending",
      "created_at": "2026-05-09T10:30:00Z",
      "expires_at": "2026-05-09T10:35:00Z"
    }
  ]
}
```

### POST /approvals/{id}/approve

**Frontend usage**: Approve a pending high-risk tool action.

#### Request

```json
{
  "reviewer": "demo-operator",
  "reason": "Approved during demo"
}
```

#### Response

```json
{
  "id": "uuid",
  "status": "approved",
  "tool_name": "issue_refund",
  "result": {"refund_id": "REF-001", "status": "processed"},
  "error": null
}
```

### POST /approvals/{id}/reject

**Frontend usage**: Reject a pending high-risk tool action.

#### Request

```json
{
  "reviewer": "demo-operator",
  "reason": "Too high value for demo"
}
```

#### Response

```json
{
  "id": "uuid",
  "status": "rejected",
  "reason": "Too high value for demo"
}
```

### GET /health

**Frontend usage**: Check backend connectivity on startup and display connection status.

#### Response

```json
{
  "status": "healthy",
  "database": "connected",
  "vector_store": "ready",
  "llm": "available"
}
```

## Frontend API Client Interface

The `api_client.py` module exposes these functions:

```python
def send_query(
    query_text: str,
    session_id: str | None = None,
    guardrails_enabled: bool | None = None,
    model_override: str | None = None,
) -> dict:
    """POST /query and return parsed response dict."""

def get_approvals() -> list[dict]:
    """GET /approvals and return list of approval items."""

def approve_action(approval_id: str, reviewer: str, reason: str) -> dict:
    """POST /approvals/{id}/approve and return result."""

def reject_action(approval_id: str, reviewer: str, reason: str) -> dict:
    """POST /approvals/{id}/reject and return result."""

def health_check() -> dict:
    """GET /health and return status dict."""
```

All functions raise `httpx.HTTPStatusError` on non-2xx responses. The Streamlit app wraps calls in try/except to display user-friendly error messages.

## Backend Implementation Notes

### Wiring `guardrails_enabled`

In `src/api/main.py`, the `/query` endpoint should:
1. Read `request.guardrails_enabled`
2. If not `None`, temporarily override `settings.tool_execution_enabled` for this request
3. Pass the effective value through to the graph invocation

### Wiring `model_override`

In `src/api/main.py`, the `/query` endpoint should:
1. Read `request.model_override`
2. If not `None`, pass as config to the graph so agent nodes use the specified model
3. If `None`, use `settings.llm_model` (existing behavior)

### Validation

- `model_override` should be validated against a whitelist of supported models
- `guardrails_enabled` is a simple boolean — no additional validation needed
- Both fields are optional and backward-compatible — existing clients unaffected
