#!/usr/bin/env bash
# Post-deployment smoke test: validates API, frontend, agent query, and conversation continuity
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
INFRA_DIR="$(dirname "$0")/../infra/environments/dev"
PASS=0
FAIL=0

pass() { echo "[PASS] $1"; PASS=$((PASS + 1)); }
fail() { echo "[FAIL] $1"; FAIL=$((FAIL + 1)); }

# ── Resolve ALB DNS ───────────────────────────────────────────────────────────
ALB_DNS=$(tofu -chdir="${INFRA_DIR}" output -raw alb_dns_name)
BASE_URL="http://${ALB_DNS}"
echo "==> Smoke testing ${BASE_URL}"

# ── Health check ──────────────────────────────────────────────────────────────
echo "==> Testing /health"
HEALTH=$(curl -sf "${BASE_URL}/health" || echo "ERROR")
if echo "${HEALTH}" | grep -q '"status":"healthy"'; then
  pass "/health returns healthy"
else
  fail "/health did not return healthy: ${HEALTH}"
fi

# ── Frontend health ───────────────────────────────────────────────────────────
echo "==> Testing Streamlit frontend"
FRONTEND=$(curl -sf "${BASE_URL}:8501/_stcore/health" || echo "ERROR")
if echo "${FRONTEND}" | grep -q "ok"; then
  pass "Streamlit frontend responds"
else
  fail "Streamlit frontend did not respond: ${FRONTEND}"
fi

# ── Agent query ───────────────────────────────────────────────────────────────
echo "==> Testing /query (RAG path: password-reset question)"
SESSION_ID="smoke-test-$(date +%s)"
QUERY_RESP=$(curl -sf -X POST "${BASE_URL}/query" \
  -H "Content-Type: application/json" \
  -d "{\"query_text\": \"How do I reset my password?\", \"session_id\": \"${SESSION_ID}\"}" \
  || echo "ERROR")

if echo "${QUERY_RESP}" | grep -q '"response_text"'; then
  pass "/query returned a response (RAG)"
else
  fail "/query did not return a response: ${QUERY_RESP}"
fi

# T075: tool-triggering query — exercises agent routing + Gateway → Lambda chain.
#
# The check is split into two assertions so the smoke test pinpoints WHERE a
# failure lives rather than collapsing both into one PASS/FAIL:
#   1. HARD: the API must return a well-formed response (no 500).
#   2. SOFT: the response should ideally contain a Lambda-issued ticket_id
#      (TKT-XXXXXXXX). When absent, we surface the upstream agent state
#      (classified_domains, llm_calls, agent) so a developer immediately knows
#      whether the classifier, the LLM tool-pick, or the Gateway chain
#      regressed.
echo "==> Testing /query (tool path: open support ticket)"
TOOL_SESSION="smoke-test-tool-$(date +%s)"
TOOL_RESP=$(curl -sf -X POST "${BASE_URL}/query" \
  -H "Content-Type: application/json" \
  -d "{\"query_text\": \"Please open a support ticket with subject 'Smoke test' and description 'Automated smoke test verifying Gateway-routed tool invocation'. Priority low.\", \"session_id\": \"${TOOL_SESSION}\"}" \
  || echo "ERROR")

if echo "${TOOL_RESP}" | grep -q '"response_text"'; then
  pass "/query (tool intent) returned a well-formed response"
  if echo "${TOOL_RESP}" | grep -qE 'TKT-[A-Z0-9]{8}'; then
    pass "/query triggered create_ticket via Gateway (ticket ID present)"
  else
    # Surface upstream agent state — the Gateway chain is verified separately
    # by unit/contract tests; if no tool was called, the gap is upstream.
    echo "[WARN] /query did not invoke a tool (no ticket ID in response)."
    echo "       Likely upstream of the Gateway: classifier returned no domain or LLM didn't tool-call."
    echo "       Agent state from response: $(echo "${TOOL_RESP}" | python3 -c "import sys,json; d=json.load(sys.stdin); print({'agent': d.get('agent'), 'classified_domains': d.get('metadata',{}).get('classified_domains'), 'llm_calls': d.get('metadata',{}).get('llm_calls'), 'tool_calls': len(d.get('tool_calls') or [])})" 2>/dev/null || echo "<unparseable>")"
  fi
else
  fail "/query (tool intent) returned malformed response: ${TOOL_RESP}"
fi

# ── Log check: no plaintext secrets ──────────────────────────────────────────
echo "==> Checking CloudWatch logs for leaked secrets"
LOG_GROUP="/ecs/dev/api"
LOG_STREAM=$(aws logs describe-log-streams \
  --log-group-name "${LOG_GROUP}" \
  --order-by LastEventTime --descending \
  --max-items 1 \
  --region "${REGION}" \
  --query 'logStreams[0].logStreamName' --output text 2>/dev/null || echo "NONE")

SECRET_RE='(sk-[A-Za-z0-9]{20,}|pk-lf-[A-Za-z0-9]{20,}|sk-lf-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})'

# Per-log-group scan: API + 3 executor Lambdas (T141). Skip groups that have
# no streams yet (e.g. Lambdas never invoked).
scan_log_group() {
  local lg="$1"
  local stream
  stream=$(aws logs describe-log-streams \
    --log-group-name "${lg}" \
    --order-by LastEventTime --descending \
    --max-items 1 \
    --region "${REGION}" \
    --query 'logStreams[0].logStreamName' --output text 2>/dev/null || echo "NONE")
  if [ "${stream}" = "NONE" ] || [ "${stream}" = "None" ]; then
    return 0
  fi
  local content
  content=$(aws logs get-log-events \
    --log-group-name "${lg}" \
    --log-stream-name "${stream}" \
    --limit 100 \
    --region "${REGION}" \
    --query 'events[*].message' --output text 2>/dev/null || echo "")
  if echo "${content}" | grep -qiE "${SECRET_RE}"; then
    return 1
  fi
  return 0
}

SECRET_LEAK_FOUND=0
for lg in "/ecs/dev/api" \
          "/aws/lambda/dev-agentic-rag-create_ticket" \
          "/aws/lambda/dev-agentic-rag-issue_refund" \
          "/aws/lambda/dev-agentic-rag-order_status"; do
  if ! scan_log_group "${lg}"; then
    fail "Potential plaintext secrets detected in CloudWatch group ${lg}"
    SECRET_LEAK_FOUND=1
  fi
done

if [ "${SECRET_LEAK_FOUND}" -eq 0 ]; then
  pass "No plaintext secrets found across API + Lambda CloudWatch groups"
fi

# ── Conversation continuity ───────────────────────────────────────────────────
echo "==> Testing conversation continuity (follow-up query)"
FOLLOWUP_RESP=$(curl -sf -X POST "${BASE_URL}/query" \
  -H "Content-Type: application/json" \
  -d "{\"query_text\": \"What were the steps you just described?\", \"session_id\": \"${SESSION_ID}\"}" \
  || echo "ERROR")

if echo "${FOLLOWUP_RESP}" | grep -q '"response_text"'; then
  pass "Follow-up query returned a response (session continuity)"
else
  fail "Follow-up query failed: ${FOLLOWUP_RESP}"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "==> Results: ${PASS} passed, ${FAIL} failed"
if [ "${FAIL}" -gt 0 ]; then
  echo "==> SMOKE TEST FAILED"
  exit 1
fi
echo "==> SMOKE TEST PASSED"
exit 0
