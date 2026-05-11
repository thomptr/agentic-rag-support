# Runbook: Diagnose a Tool Failure in Production

**SC-005 target**: root-cause a failed `/query` from logs + traces in **under 5 minutes**.

This runbook covers the most common failure surface: an executor tool (Gateway-routed Lambda) returns an error, the agent reports it back, and a user complains. There are three observability sources to triangulate from — checking them in this order matches the actual flow of the request.

---

## 1. Confirm the user-facing failure (≤ 30s)

Get the user's session ID, then `curl` the same query and inspect the response:

```bash
ALB_DNS=$(cd infra/environments/dev && tofu output -raw alb_dns_name)
curl -s -X POST "http://${ALB_DNS}/query" \
  -H "Content-Type: application/json" \
  -d '{"query_text": "<the user query>", "session_id": "<their session>"}' | jq .
```

Look at `response_text`. If it contains "Action Results: • [tool_name] Failed: <error_code>", you've confirmed a tool failure and identified the **tool** + **error_code** (e.g., `business_rule_violation`).

## 2. Find the agent-side parent span in Langfuse (≤ 2 min)

The agent emits one Langfuse trace per `/query`. Search by `session_id`:

- Langfuse UI: filter by `metadata.session_id = <session>` in the last hour.
- API equivalent: `lf.api.trace.list(filter={"metadata.session_id": session_id})`.

Open the trace. The parent span (`tool.dispatch` or similar) should show:
- `input`: tool name + parameters (redacted per `langfuse_client.REDACT_KEYS`)
- `output`: the failure envelope (status="error", error_code, error_message)
- `metadata.tool_name`: which tool failed

If you see the parent span but no child span beneath it, **the call never reached the Lambda** — jump to "Gateway path issues" below.

## 3. Find the Lambda-side child span (≤ 1 min)

In the same trace, find the child observation with `name = "tool.<tool_name>"`. Its `metadata.aws_request_id` is the key cross-reference: paste it into the CloudWatch log group `/aws/lambda/dev-agentic-rag-<tool_name>` to locate the exact invocation.

## 4. Pull the Lambda log lines (≤ 1 min)

```bash
TOOL=issue_refund   # or create_ticket / order_status
REQUEST_ID=<from-langfuse-metadata>

aws logs filter-log-events \
  --log-group-name "/aws/lambda/dev-agentic-rag-${TOOL}" \
  --filter-pattern "\"${REQUEST_ID}\"" \
  --region us-east-1 \
  --query 'events[].message' --output text
```

The Lambda emits `tool.attempt` + `tool.failed` JSON-line events (see `lambdas/shared/audit_emitter.py`). The `tool.failed` event has the precise `error_code` and `error_message` that drove the response.

## Gateway path issues (when there's no child span)

The agent's parent span exists but Lambda was never invoked. Likely causes:

| Symptom | Likely cause | Fix |
|---|---|---|
| Agent parent span shows `error_code=jwt_fetch_failed` | Cognito M2M client_secret rotated or revoked | Re-run quickstart Step 11 (rotation) |
| Agent shows `error_code=gateway_401` after refresh+retry | Gateway authorizer rejects token (scope mismatch?) | Verify `allowed_audience` in Gateway authorizer matches the scope in the token |
| Agent shows `error_code=gateway_504` | Lambda timing out OR Gateway can't reach target | Check Lambda CloudWatch for cold-start issues; verify `aws_lambda_permission.gateway_invoke` is intact |
| Agent shows `gateway_500` | Most likely the Gateway target schema/auth config is broken | Re-run `scripts/register-gateway-targets.sh` |

## Chaos-mode toggle (drill / SC-005 verification)

To exercise this runbook against a real failure without breaking anything, flip the `issue_refund` Lambda into forced-failure mode:

```bash
aws lambda update-function-configuration \
  --function-name dev-agentic-rag-issue_refund \
  --environment "Variables={TOOL_NAME=issue_refund,LANGFUSE_HOST=...,LANGFUSE_SECRET_REF=...,LANGFUSE_PUBLIC_REF=...,LOG_LEVEL=INFO,FAIL_MODE=business_rule_violation}" \
  --region us-east-1
# … run your timed drill, then revert by repeating without FAIL_MODE in the variables block
```

The chaos handler is wired in `lambdas/issue_refund/handler.py` (`_KNOWN_FAIL_MODES`). It only honors `business_rule_violation` today; add more modes to that set if other failure paths need rehearsal.
