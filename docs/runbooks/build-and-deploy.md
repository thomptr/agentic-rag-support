# Runbook: Build and Deploy

Deploy a new build of the AWS-hosted agentic-rag-support system. Covers the
three container images (agent, API, frontend) and the three Lambda zips +
shared layer.

**Prerequisites**: `docker` (with buildx + a `linux/arm64` capable builder),
`aws` CLI with credentials for account `791642260585`, `tofu`, and the
project venv (`make` targets assume `.venv/bin/python` etc.).

**Image architecture**: everything in this stack runs on **ARM64**:
- AgentCore Runtime: ARM64-only per the AWS service
- ECS Fargate API + Frontend: configured for ARM64 (Graviton, ~20% cost win)
- Lambda functions: ARM64 (smaller cold-start than x86 in this profile)

Always pass `--platform linux/arm64 --provenance=false --sbom=false` to
`docker buildx`. The `--provenance=false` matters: AgentCore Runtime
silently rejects multi-arch manifests that include an `unknown/unknown`
provenance entry.

---

## 1. Code health (must pass before any deploy)

```bash
make lint && make test-unit && make test-int
```

Expected: lint clean, **313 unit + 63 integration passed**, plus 1 + 2
gated-skipped (RUN_INTEGRATION=1 tests).

If any of these fail, fix in code — do not deploy.

---

## 2. Pick what you're deploying

The stack has six independent build artifacts. Most changes only need a
subset:

| Change | Artifacts to rebuild |
|---|---|
| Agent source (`src/agents/`, `src/graph/`, `src/rag/`, `src/entrypoint/`, `src/tools/` excluding the Lambdas) | agent image |
| API source (`src/api/`) | API image |
| Streamlit frontend (`src/frontend/`) | frontend image |
| One executor tool's logic or schema (`lambdas/<tool>/`) | that tool's zip |
| Shared Lambda layer (`lambdas/shared/`) | shared layer + all three tool zips (they depend on the layer's content hash via OpenTofu) |
| Infra (`infra/`) | none — `tofu apply` only |

When in doubt, rebuild everything — it takes ~5 minutes total.

---

## 3. Login to ECR (always)

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR=${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin "${ECR}"
```

ECR login tokens expire after 12h. If `docker push` returns `denied: ...`,
re-run this block.

---

## 4. Build + push container images

### Agent image

```bash
docker buildx build --platform linux/arm64 --provenance=false --sbom=false \
  -f docker/Dockerfile.agent \
  -t ${ECR}/agentic-rag-agent:latest \
  --push .
```

### API image

```bash
docker buildx build --platform linux/arm64 --provenance=false --sbom=false \
  -f docker/Dockerfile.api \
  -t ${ECR}/agentic-rag-api:latest \
  --push .
```

### Frontend image

```bash
docker buildx build --platform linux/arm64 --provenance=false --sbom=false \
  -f docker/Dockerfile.frontend \
  -t ${ECR}/agentic-rag-frontend:latest \
  --push .
```

---

## 5. Build + apply Lambdas

The Lambda layer + per-tool zips are produced by build scripts and then
picked up by `tofu apply` via the `aws_lambda_function.tool[*]` resource's
`source_code_hash`. Building doesn't deploy; `tofu apply` does.

```bash
# (a) Rebuild the shared layer (~7 MB; pulls langfuse, powertools, etc. for arm64)
bash scripts/build-lambda-layer.sh

# (b) Rebuild each tool's zip
for t in create_ticket issue_refund order_status; do
  bash scripts/build-lambda.sh "$t"
done

# (c) Apply infra — uploads layer + new tool versions to AWS, wires Gateway targets
cd infra/environments/dev
tofu apply -var dev_public_ip_cidr=$(curl -s checkip.amazonaws.com)/32
cd -
```

The script `scripts/register-gateway-targets.sh` reconciles Gateway Targets
to match the current Lambda set. `tofu apply` does **not** call it — run it
explicitly when a new tool is added or a tool's schema changes:

```bash
REPO_ROOT=$(pwd) bash scripts/register-gateway-targets.sh
```

---

## 6. Force runtime / service to pull the new images

ECR pushes don't automatically restart anything. You have to nudge:

### AgentCore Runtime (after rebuilding the agent image)

The runtime caches the image at startup. Force a new version:

```bash
.venv/bin/python <<'PY'
import boto3, time
ac = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
rid = "dev_agentic_rag_agent-zL8aePA0As"  # adjust per env
rt = ac.get_agent_runtime(agentRuntimeId=rid)
ac.update_agent_runtime(
    agentRuntimeId=rid,
    description=rt.get("description", ""),
    roleArn=rt["roleArn"],
    agentRuntimeArtifact=rt["agentRuntimeArtifact"],
    networkConfiguration=rt["networkConfiguration"],
    protocolConfiguration=rt.get("protocolConfiguration", "HTTP"),
    environmentVariables=rt.get("environmentVariables", {}),
)
for _ in range(60):
    s = ac.get_agent_runtime(agentRuntimeId=rid).get("status")
    print(time.strftime("%H:%M:%S"), s)
    if s == "READY": break
    if s and s.startswith(("FAILED","ERROR")): break
    time.sleep(5)
PY
```

The DEFAULT endpoint's `liveVersion` follows the runtime version automatically
— you do not need to update the endpoint separately. Typical wait: 15-30 s.

### ECS API / Frontend (after rebuilding either image)

```bash
aws ecs update-service \
  --cluster dev-agentic-rag --service dev-api \
  --force-new-deployment --region us-east-1
aws ecs update-service \
  --cluster dev-agentic-rag --service dev-frontend \
  --force-new-deployment --region us-east-1
```

ECS performs a rolling deploy: launches a new task, waits for it to pass ALB
health checks, then drains the old one. Watch progress:

```bash
aws ecs describe-services --cluster dev-agentic-rag --services dev-api \
  --region us-east-1 \
  --query 'services[0].deployments[?status==`PRIMARY`].rolloutState' --output text
```

Wait for `COMPLETED`. Typical: 3-10 min depending on container startup time.

---

## 7. Verify

```bash
bash scripts/smoke-test.sh
```

Expect **6/6 PASS**. The tool-intent probe may show `[WARN] no ticket ID in
response` — that signals the LLM tool-pick gap (separate from deployment
health). All numbered tests should pass.

If any test fails, see "Common failure modes" below.

---

## Common failure modes (in order of how often we hit them)

### `403 Forbidden` from AgentCore Runtime invocations

Two distinct causes — check both:

1. **The DEFAULT endpoint version drifted.** `list_agent_runtime_endpoints`
   should show `liveVersion` matching the current runtime version. If
   stale, the runtime update didn't propagate; retry the boto3 update.
2. **IAM policy resource doesn't match the actual ARN.** The ECS task role
   policy must cover both
   `runtime/<runtime-id>` and the endpoint sub-resource
   `runtime/<runtime-id>/runtime-endpoint/DEFAULT`. The wildcard
   `runtime/<runtime-id>/*` matches both. Check with:
   ```bash
   aws iam get-role-policy --role-name dev-agentic-rag-ecs-task-role \
     --policy-name dev-agentic-rag-ecs-task-agentcore --region us-east-1
   ```

### ECS task crashloops, `EssentialContainerExited`

Almost always a Python import error from a new code change shipped without
the matching dependency. Pull the failing task's startup log:

```bash
LATEST=$(aws ecs list-tasks --cluster dev-agentic-rag --service-name dev-api \
  --desired-status STOPPED --max-results 1 --region us-east-1 \
  --query 'taskArns[0]' --output text)
TASK_ID=$(echo "$LATEST" | rev | cut -d/ -f1 | rev)
aws logs get-log-events --log-group-name /ecs/dev/api \
  --log-stream-name "ecs/api/$TASK_ID" --region us-east-1 \
  --start-from-head --limit 30 --query 'events[].message' --output text \
  | tr '\t' '\n' | grep -E "Error|Module|Traceback"
```

Common: API or frontend image imports something only the agent has (e.g.
`langgraph`). Fix the import or add the dep to that container's Dockerfile,
then rebuild.

### Lambda `ModuleNotFoundError: No module named 'lambdas'`

The Lambda zip was built with the wrong layout — files were rooted at the
zip top instead of under `lambdas/<tool>/`. Check:

```bash
python3 -m zipfile -l lambdas/_dist/issue_refund.zip | head -5
```

The first entries should be `lambdas/`, `lambdas/issue_refund/`,
`lambdas/issue_refund/handler.py`. If `handler.py` is at the top instead,
rebuild via `scripts/build-lambda.sh` (the script is the source of truth).

Also: do not put `lambdas/__init__.py` in **both** the function zip and the
layer — that makes `lambdas` a regular package and the layer's contribution
gets shadowed. Use a namespace package (no top-level `__init__.py`). The
build scripts do this correctly; manual edits sometimes regress it.

### `gateway_url_unset` from the orchestrator

`settings.gateway_url` is empty in the deployed runtime. Verify
`infra/modules/agentcore/main.tf` passes `GATEWAY_URL` through
`environment_variables`, and that `tofu apply` ran after the Gateway
resource came up (the URL is computed from the Gateway, so the runtime
must update afterwards).

### Gateway Target `status=FAILED`

Usually a Lambda permission issue. The `aws_lambda_permission.gateway_invoke`
resources in `infra/modules/lambdas/main.tf` grant
`bedrock-agentcore.amazonaws.com` the right to invoke each tool's Lambda;
if they got removed or the principal changed, the Gateway's invocation is
denied. Run `tofu apply` to reconcile.

### Smoke tests pass except `/query` returns 500

Look at `/ecs/dev/api` CloudWatch logs for the actual exception. Most likely
causes (in rough order): missing OpenAI key in Secrets Manager, expired RDS
password (the entrypoint refreshes it at cold start so a runtime version
bump usually fixes this), Cognito JWT misconfig (Gateway 401 cascade),
or new-code regression.

---

## Architecture recap (so the order above makes sense)

```
                           ┌──────────────────────────────────┐
                           │   AgentCore Runtime (Graviton)   │
ECR ── agent:latest ──────▶│   pulls on update_agent_runtime  │
                           └─────────────┬────────────────────┘
                                         │ MCP + JWT (Cognito)
                                         ▼
                          ┌──────────────────────────────┐
                          │   AgentCore Tool Gateway     │
                          └──────┬──────┬──────┬─────────┘
                                 │      │      │
                                 ▼      ▼      ▼
                          create  issue  order_status
                           ticket  refund     ┐
ECR ── lambda layer ──────────────────────────┘
ECR ── per-tool zips ─────  (Lambda functions, ARM64)

                                                 ┌────────────────────────┐
                                                 │   ALB (port 80, 8501)   │
                                                 └──────┬──────────┬───────┘
                                                        │          │
                                                        ▼          ▼
                                                  dev-api    dev-frontend
                                                  (FastAPI)  (Streamlit)
ECR ── api:latest ──── pulled on ECS force-new-deployment   ECR ── frontend:latest
```

The API forwards every `/query` to AgentCore Runtime over SigV4-signed
HTTPS. The Runtime invokes the LangGraph graph, which (when a tool is
chosen) calls Gateway → Lambda. The deploy order matters because a new
agent image can rely on new infra (Cognito, Gateway, secrets) that's
provisioned by `tofu apply`.
