# Contract: Executor Tool Lambda — Invocation

**Feature**: 005-aws-agentcore-deployment (refactor scope)
**Date**: 2026-05-10

This contract governs the request/response shape every executor-tool Lambda accepts when invoked by AgentCore Tool Gateway. All three Lambdas (`create_ticket`, `issue_refund`, `order_status`) implement this contract; tool-specific fields go inside `parameters`.

## Request (Gateway → Lambda)

```json
{
  "tool_name": "create_ticket",
  "parameters": { /* tool-specific Pydantic-validated object */ },
  "trace_meta": {
    "trace_id":        "f1c8a4c8-7b6e-4f2a-9f8a-12d3e4f5a6b7",
    "parent_span_id":  "a1b2c3d4-e5f6-7890-1234-567890abcdef",
    "session_id":      "smoke-test-1747000000",
    "run_id":          "1de60bd7-a3df-4e9d-bca0-7f5b2e8a1c3d"
  }
}
```

### Field rules

| Field | Type | Required | Validation |
|---|---|---|---|
| `tool_name` | string | yes | Must equal the Lambda's `TOOL_NAME` env var. Mismatch → 400 `wrong_tool_target`. |
| `parameters` | object | yes | Validated by the tool's Pydantic `*Input` model (e.g., `CreateTicketInput`). Validation failure → 400 `invalid_parameters` with field-level details. |
| `trace_meta.trace_id` | UUID string | yes | If missing/empty → 400 `missing_trace_context`. |
| `trace_meta.parent_span_id` | UUID string | yes | Same as above. |
| `trace_meta.session_id` | UUID string | yes | Logged but not validated structurally. |
| `trace_meta.run_id` | UUID string | yes | Logged but not validated structurally. |

Unknown top-level fields are ignored. Unknown fields inside `parameters` cause a 400 (Pydantic strict mode).

## Response — success (HTTP 200 equivalent)

```json
{
  "status": "success",
  "result": { /* tool-specific Pydantic-validated object */ },
  "trace_id": "f1c8a4c8-7b6e-4f2a-9f8a-12d3e4f5a6b7"
}
```

- `result` matches the tool's Pydantic `*Output` model (e.g., `CreateTicketOutput`).
- `trace_id` echoes the request's `trace_meta.trace_id` so the agent can verify trace continuity end-to-end.

## Response — error (HTTP 4xx/5xx equivalent)

```json
{
  "status": "error",
  "error_code": "invalid_parameters",
  "error_message": "ticket_subject is required",
  "details": { /* optional, structured */ },
  "trace_id": "f1c8a4c8-7b6e-4f2a-9f8a-12d3e4f5a6b7"
}
```

### Error code enumeration

| `error_code` | Meaning | HTTP-equivalent |
|---|---|---|
| `invalid_parameters` | Pydantic validation failed | 400 |
| `missing_trace_context` | `trace_meta.trace_id` or `parent_span_id` absent/empty | 400 |
| `wrong_tool_target` | `tool_name` does not match the Lambda's bound tool | 400 |
| `business_rule_violation` | Tool-internal rule rejected the request (e.g., refund_amount over the cap as evaluated by tool logic, not by guardrails) | 422 |
| `external_dependency_unavailable` | Tool depends on an external system (e.g., ticketing API) that returned 5xx or timed out | 503 |
| `internal_error` | Uncaught exception in handler | 500 |

The Gateway maps these to MCP `tool_use_error` / `tool_result_error` semantics with the `error_code` preserved verbatim in metadata.

## Tracing requirements

Every Lambda invocation MUST:

1. **At cold start** (top-level module init):
   - Initialize Langfuse SDK with credentials read from Secrets Manager (`dev/agentic-rag/langfuse-secret-key` + `langfuse-public-key`). Failure here MUST emit a CloudWatch `ERROR` log and set a module-level `LANGFUSE_INIT_FAILED = True` flag.
   - Construct a singleton structlog logger bound with `tool_name`, `aws_request_id`, `aws_lambda_log_group`.

2. **Per invocation**:
   - Extract `trace_meta` from the event.
   - Create a Langfuse child span:
     - `trace_id = trace_meta.trace_id`
     - `parent_observation_id = trace_meta.parent_span_id`
     - `name = "tool.<tool_name>"`
     - `input = parameters` (after redaction — see below)
     - `output = result` on success, `{error_code, error_message}` on error
     - `metadata = {session_id, run_id, aws_request_id, lambda_arn}`
   - Flush Langfuse before the handler returns (Lambda freezes the runtime between invocations and Langfuse uses background threads).

3. **Redaction**: Never log raw values for fields named `password`, `card_number`, `cvv`, or `secret`. Implement once in the shared layer's `langfuse_client.py`.

## Idempotency

- `order_status` is naturally idempotent (read-only).
- `create_ticket` and `issue_refund` MUST accept an optional `parameters.idempotency_key` string. If present and equal to a prior call's key within a 5-minute window, the Lambda returns the original response. Storage for idempotency state can be in-memory per Lambda container for the POC (good enough since duplicates within seconds will likely hit the same warm container); upgrade to DynamoDB if real cross-container dedup becomes a need.

## Contract test obligations (Constitution III)

Every Lambda's `tests/test_handler.py` MUST include:

- `test_input_schema_matches_target_definition` — load the tool definition from the Gateway target's input_schema and compare against the Pydantic-derived JSON Schema.
- `test_missing_trace_context_returns_400` — invoke handler without `trace_meta`, assert `status=error, error_code=missing_trace_context`.
- `test_wrong_tool_target_returns_400` — invoke with mismatched `tool_name`, assert error.
- `test_happy_path_emits_langfuse_child_span` — invoke with stub Langfuse client, assert one child span emitted with the right `trace_id` / `parent_observation_id`.
- `test_handler_idempotency_window` — applies to `create_ticket` + `issue_refund` only.
