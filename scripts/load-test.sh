#!/usr/bin/env bash
# Load test: fire N concurrent /query requests at the deployed agent and assert
# all complete within a per-request latency budget. Default N=10, budget=30s
# to validate SC-003 (10 concurrent users, all <30s, zero failures).
#
# Usage:
#   bash scripts/load-test.sh                # 10 concurrent, 30s budget
#   N=20 BUDGET_S=45 bash scripts/load-test.sh

set -euo pipefail

N="${N:-10}"
BUDGET_S="${BUDGET_S:-30}"
REGION="${AWS_REGION:-us-east-1}"
INFRA_DIR="$(dirname "$0")/../infra/environments/dev"

ALB_DNS=$(tofu -chdir="${INFRA_DIR}" output -raw alb_dns_name)
BASE_URL="http://${ALB_DNS}"
RUN_ID="loadtest-$(date +%s)"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "${TMPDIR}"' EXIT

echo "==> Load test: N=${N} concurrent /query requests, budget=${BUDGET_S}s, base=${BASE_URL}"

# Rotating prompts so the cache doesn't trivialize every request.
PROMPTS=(
  "How do I reset my password?"
  "What's your refund policy?"
  "How do I cancel my subscription?"
  "I need help with API rate limits."
  "How can I export my account data?"
  "Why was I charged twice last month?"
  "Can I change my plan mid-cycle?"
  "How does multi-factor authentication work?"
  "What's the procedure for a refund?"
  "How do I add a teammate to my account?"
)

# Fire all N requests in parallel; write status + latency to a per-request file.
START=$(date +%s)
for i in $(seq 1 "${N}"); do
  prompt="${PROMPTS[$(((i - 1) % ${#PROMPTS[@]}))]}"
  (
    # Disable strict-mode inside the subshell — curl exits non-zero on HTTP
    # error or timeout, and `set -e` would kill us before writing the result
    # file. We capture the curl exit + http_code separately below.
    set +e
    t0=$(date +%s.%N)
    code=$(curl -s -o "${TMPDIR}/body_${i}" -w '%{http_code}' \
      --max-time "${BUDGET_S}" \
      -X POST "${BASE_URL}/query" \
      -H "Content-Type: application/json" \
      -d "{\"query_text\": \"${prompt}\", \"session_id\": \"${RUN_ID}-${i}\"}" 2>/dev/null)
    curl_rc=$?
    t1=$(date +%s.%N)
    # On timeout/connection-failure curl emits no body and exits 28+; force a
    # "000" code so the result file is always well-formed.
    [ -z "${code}" ] && code="000"
    [ "${curl_rc}" -ne 0 ] && [ "${code}" = "200" ] && code="000"
    latency=$(awk -v a="${t1}" -v b="${t0}" 'BEGIN {printf "%.3f", a-b}')
    echo "${i} ${code} ${latency}" > "${TMPDIR}/result_${i}"
  ) &
done
wait
END=$(date +%s)

# Collect + summarize.
PASS=0
FAIL=0
TIMEOUT=0
LATENCIES=()
for i in $(seq 1 "${N}"); do
  read -r _ code latency < "${TMPDIR}/result_${i}"
  LATENCIES+=("${latency}")
  if [ "${code}" = "200" ]; then
    PASS=$((PASS + 1))
  elif [ "${code}" = "000" ]; then
    TIMEOUT=$((TIMEOUT + 1))
    FAIL=$((FAIL + 1))
    echo "  [TIMEOUT or no-response] request ${i}, latency=${latency}s"
  else
    FAIL=$((FAIL + 1))
    body_excerpt=$(head -c 120 "${TMPDIR}/body_${i}" 2>/dev/null || echo "")
    echo "  [HTTP ${code}] request ${i}, latency=${latency}s, body=${body_excerpt}"
  fi
done

# Compute p50/p95/max.
SORTED=$(printf '%s\n' "${LATENCIES[@]}" | sort -n)
P50=$(echo "${SORTED}" | awk -v n="${N}" 'NR==int(n*0.5)+1{print; exit}')
P95=$(echo "${SORTED}" | awk -v n="${N}" 'NR==int(n*0.95)+1{print; exit}')
MAX=$(echo "${SORTED}" | tail -1)

echo
echo "==> Results"
echo "  total wall time: $((END - START))s"
echo "  passed: ${PASS}/${N}"
echo "  failed: ${FAIL}  (timeouts: ${TIMEOUT})"
echo "  p50: ${P50}s   p95: ${P95}s   max: ${MAX}s"
echo

# SC-003 assertion: all requests succeed AND max <= BUDGET_S.
if [ "${FAIL}" -gt 0 ]; then
  echo "==> SC-003 FAILED: ${FAIL} request(s) did not succeed"
  exit 1
fi
if awk -v m="${MAX}" -v b="${BUDGET_S}" 'BEGIN {exit !(m+0 > b+0)}'; then
  echo "==> SC-003 FAILED: max latency ${MAX}s exceeded budget ${BUDGET_S}s"
  exit 1
fi
echo "==> SC-003 PASSED: ${N} concurrent requests, all <${BUDGET_S}s"
