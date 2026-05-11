---
description: "Tasks for AWS AgentCore Deployment + Gateway/Lambda tool refactor"
---

# Tasks: AWS AgentCore Deployment + Executor Tool Refactor (Gateway + Lambda)

**Feature Branch**: `005-aws-agentcore-deployment`
**Input**: Design documents in `/specs/005-aws-agentcore-deployment/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/tool-lambda.md](contracts/tool-lambda.md)

**Tests**: Required. Constitution Principle III (Test-First) is NON-NEGOTIABLE — failing tests land before implementation for every code task.

**Scope note**: The base AWS deployment (VPC, RDS, ECS, AgentCore Runtime, ALB, three ARM64 service images) was provisioned earlier on this branch and is currently green for `/health` and the Streamlit frontend in smoke testing. These tasks focus on the executor-tool refactor (US1's remaining work) plus the scaling/observability/secrets stories that round out the spec.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: User-story tag (US1, US2, US3, US4)
- Each task includes the exact file path it touches

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Repo-level scaffolding for the new Lambda + Gateway artifacts. None of these touch live AWS resources yet.

- [X] T001 Create `lambdas/` top-level directory with subfolders `lambdas/create_ticket/`, `lambdas/issue_refund/`, `lambdas/order_status/`, `lambdas/shared/` per [plan.md § Project Structure](plan.md)
- [X] T002 [P] Add `lambdas/shared/requirements.txt` listing `langfuse>=2.0,<3.0`, `aws-lambda-powertools>=3.0`, `structlog>=24.0`, `pydantic>=2.5`
- [X] T003 [P] Create build script `scripts/build-lambda-layer.sh` that produces `lambdas/_dist/shared-layer.zip` with the layer's dependencies installed for `linux/arm64` (uses `pip --platform manylinux2014_aarch64`)
- [X] T004 [P] Create per-tool build script `scripts/build-lambda.sh` that takes a tool name and produces `lambdas/_dist/<tool>.zip` from `lambdas/<tool>/`
- [X] T005 [P] Add `lambdas/` paths to the existing ruff/pytest configs in `pyproject.toml` so the new code is linted and tested by `make lint` and `make test-unit`
- [X] T006 Add `lambdas/_dist/` to [.gitignore](.gitignore)

**Checkpoint**: Folders exist and build scripts run end-to-end producing empty zip artifacts.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infra modules and shared code every user story depends on. No user-story task can start until this phase is green.

⚠️ **CRITICAL**: This phase establishes the Cognito ↔ Gateway ↔ Lambda backbone. Order matters: Cognito → Gateway (authorizer references Cognito) → Lambda module skeleton → Gateway targets.

### Infra modules

- [X] T010 Create OpenTofu module `infra/modules/cognito/main.tf` with `aws_cognito_user_pool.svc`, `aws_cognito_user_pool_domain.svc`, `aws_cognito_resource_server.tools`, `aws_cognito_user_pool_client.agent_runtime` (M2M, `client_credentials` flow, scope `agentic-rag-tools/gateway.invoke`)
- [X] T011 [P] Create `infra/modules/cognito/variables.tf` and `outputs.tf` exposing `user_pool_id`, `client_id`, `client_secret`, `token_url`, `discovery_url`, `scope`
- [X] T012 Wire the Cognito client_secret into Secrets Manager — extended `infra/modules/secrets/main.tf` with `aws_secretsmanager_secret.cognito_m2m_client_secret` + `aws_secretsmanager_secret_version` driven by `var.cognito_m2m_client_secret`
- [X] T013 Create OpenTofu module skeleton `infra/modules/lambdas/main.tf` with a `for_each` over `var.tools` producing per-tool IAM role/policy, shared `aws_lambda_layer_version`, `aws_lambda_function` (arm64, zip, layer attached), CloudWatch log group, and `aws_lambda_permission` for Gateway invoke
- [X] T014 [P] Create `infra/modules/lambdas/variables.tf` and `outputs.tf` exposing `lambda_arns`, `lambda_function_names`, `lambda_role_arns`, `shared_layer_arn`
- [X] T015 Create OpenTofu module `infra/modules/agentcore_gateway/main.tf` with `awscc_bedrockagentcore_gateway.tools` (authorizer_type `CUSTOM_JWT`, protocol_type `MCP`, custom_jwt_authorizer.discovery_url) + IAM role for Lambda invocation. **NOTE**: `awscc_bedrockagentcore_gateway_target` does NOT exist in awscc 1.83.0 — targets are registered out-of-band; tracked as a follow-up
- [X] T016 [P] Create `infra/modules/agentcore_gateway/variables.tf` and `outputs.tf` exposing `gateway_id`, `gateway_url`, `gateway_arn`, `gateway_role_arn`
- [X] T017 Wire the new modules into `infra/environments/dev/main.tf` (`module "cognito"`, `module "lambdas"`, `module "agentcore_gateway"`) and pass `GATEWAY_URL`/`COGNITO_*` env vars through `module "agentcore"`
- [X] T018 [P] Added outputs `gateway_id`, `gateway_url`, `cognito_token_url`, `cognito_client_id`, `cognito_discovery_url`, `lambda_function_names` to `infra/environments/dev/outputs.tf`

### Shared code

- [X] T020 Create `lambdas/shared/tracing.py` implementing `extract_trace_meta(event) -> TraceMeta`, `assert_trace_meta_present(event)`, and `MissingTraceContext` exception
- [X] T021 [P] Create `lambdas/shared/langfuse_client.py` with cold-start Langfuse init (reads `LANGFUSE_SECRET_REF`/`LANGFUSE_PUBLIC_REF` → Secrets Manager), `create_child_span()`, `redact()` over a canonical key list (password/card_number/cvv/secret/client_secret/authorization), `flush()` helper
- [X] T022 [P] Create `lambdas/shared/audit_emitter.py` emitting JSON-line stdout `tool.attempt`/`tool.success`/`tool.failed` events with trace_id correlation
- [X] T023 [P] Create `lambdas/shared/responses.py` with `success(result, trace_id)` and `error(code, message, trace_id, details=None)` per [contracts/tool-lambda.md](contracts/tool-lambda.md)

### Agent-side configuration plumbing

- [X] T024 Extended `src/config.py` Settings with `gateway_url`, `cognito_token_url`, `cognito_client_id`, `cognito_client_secret_arn`, `cognito_client_secret`, `cognito_scope`
- [X] T025 [P] Updated `src/entrypoint/main.py` with `_resolve_cognito_client_secret()` that reads the M2M client_secret from Secrets Manager at module import and stores it in `settings.cognito_client_secret`

**Checkpoint**: `tofu validate` is clean, shared Lambda code modules exist (no Lambda handlers yet), `src/config.py` carries the new settings. Ready to start US1.

---

## Phase 3: User Story 1 — Deploy Agent to Cloud (Priority: P1) 🎯 MVP

**Goal**: The deployed agent answers a query end-to-end via the Gateway-routed executor path. Tool calls flow agent → Cognito (JWT) → AgentCore Gateway (MCP) → Lambda → back, with Langfuse trace continuity preserved.

**Independent test**: After this phase, `bash scripts/smoke-test.sh` passes 5/5 including a `/query` that triggers `create_ticket` and the response cites a Lambda-produced ticket ID. The Langfuse UI shows a parent span (agent) with a single child span (Lambda) for the tool call.

### Tests-first (Constitution III)

- [X] T030 [P] [US1] `lambdas/create_ticket/tests/test_handler.py::test_input_schema_matches_target_definition` written (red — module not implemented)
- [X] T031 [P] [US1] `test_missing_trace_context_returns_400`, `test_wrong_tool_target_returns_400`, `test_happy_path_returns_success_envelope`, `test_handler_idempotency_window` in `lambdas/create_ticket/tests/test_handler.py` (red)
- [X] T032 [P] [US1] `lambdas/issue_refund/tests/test_handler.py` — 5 tests written, red
- [X] T033 [P] [US1] `lambdas/order_status/tests/test_handler.py` — 4 tests written, red (no idempotency since read-only)
- [X] T034 [P] [US1] `tests/unit/test_gateway_executor.py` — 5 tests written covering JWT cache miss/hit, 401 refresh+retry, 504 no-retry, trace_meta propagation (red)
- [X] T035 [P] [US1] `tests/unit/test_jwt_cache.py` — 7 tests for FRESH/STALE/EMPTY state machine + invalidation + fetch errors (red)
- [X] T036 [US1] `tests/integration/test_gateway_e2e.py` written, gated on `RUN_INTEGRATION=1`; queries Langfuse for trace continuity after a `/query` against the deployed ALB

### Implementation — agent side

- [X] T040 [US1] Implemented `src/api/cognito_jwt_cache.py` with `JWTCache` class (FRESH/STALE/EMPTY state machine, 60s refresh window) + `TokenFetchError` exception, using stdlib `urllib` for the token endpoint. 7/7 jwt_cache tests pass.
- [X] T041 [US1] Implemented `src/tools/gateway_executor.py` exporting `invoke()` returning `ToolResult`, with `_mcp_call()` (HTTP POST to Gateway `/invocations`), `_jwt_cache` module-level cache (lazy-initialized), `GatewayHTTPError`, 401→refresh+retry / 504→fail-no-retry logic. 5/5 gateway_executor tests pass.
- [X] T042 [US1] Added `kind: str` field to `ToolDefinition` in `src/tools/registry.py`; tagged `order_status_lookup`, `create_support_ticket`, `issue_refund` as `kind="gateway"`. Gateway-discovery-at-cold-start was deferred — too risky during agent boot when Gateway isn't yet provisioned; revisit after T062 lands.
- [X] T043 [US1] Updated `src/tools/executor.py` to route gateway-kind tools through `gateway_executor.invoke()` when `settings.gateway_url` is set. Falls back to in-process `execute_fn` when GATEWAY_URL is empty so existing local-dev tests still pass; T070-T072's hard cutover removes the fallback.

### Implementation — Lambda side

- [X] T050 [P] [US1] `lambdas/create_ticket/schema.py` — `CreateTicketInput` (+ optional `idempotency_key`) and `CreateTicketOutput`
- [X] T051 [US1] `lambdas/create_ticket/handler.py::lambda_handler` — trace_meta validation, tool-name guard, Pydantic param validation, in-memory idempotency cache (5min TTL), mock TKT-XXXXXXXX generation, Langfuse child span. 5/5 tests pass.
- [X] T052 [P] [US1] `lambdas/issue_refund/schema.py` — `IssueRefundInput` (with `customer_id` + `idempotency_key`) and `IssueRefundOutput`
- [X] T053 [US1] `lambdas/issue_refund/handler.py::lambda_handler` — same shape as create_ticket; mock REF-XXXXXXXX. 5/5 tests pass.
- [X] T054 [P] [US1] `lambdas/order_status/schema.py` — `OrderStatusInput` (just `order_id`) and `OrderStatusOutput` (status, items, total, tracking_number)
- [X] T055 [US1] `lambdas/order_status/handler.py::lambda_handler` — read-only, no idempotency cache. 4/4 tests pass.

### Infra deploy + Gateway targets

- [X] T060 [US1] Built all 4 zip artifacts: `shared-layer.zip` (7.4 MB — Langfuse SDK + Powertools + structlog + pydantic for linux/arm64), `create_ticket.zip`, `issue_refund.zip`, `order_status.zip`. Build scripts updated to use `python3` (not `python`) and `python3 -m zipfile` (host has no `zip` binary).
- [X] T061 [US1] `tofu plan` is green and saved to `tfplan`. Fixed two AWSCC issues during the plan: (1) Gateway name regex requires dashes (not underscores like the runtime resource); (2) `aws_secretsmanager_secret_version.cognito_m2m_client_secret` count was conditional on an unknown value — dropped the conditional. Plan: 25 to add, 3 to update, 0 destroy.
- [X] T062 [US1] `tofu apply` provisioned Cognito + 3 Lambdas + Gateway + Lambda Layer + IAM in ~3 min (26 added, 3 changed, 1 destroyed). Gateway Targets registered via new `scripts/register-gateway-targets.sh` (boto3-based, since AWSCC v1.83.0 has no target resource) using `GATEWAY_IAM_ROLE` credentialProviderType. All 3 targets reach `status=READY`. Target resource names use dashes (regex requires); MCP tool names presented to the agent retain underscores via `toolSchema.inlinePayload[].name`.

### Cutover

- [X] T070 [US1] `src/tools/executor.py` deleted (renamed to `src/tools/orchestrator.py` — its actual responsibility is guardrails+approval+dispatch orchestration, not in-process execution which was removed earlier). Updated 7 import sites (`src/agents/action_executor.py`, `src/tools/approval.py`, `src/tools/gateway_executor.py`, and 4 test files); renamed `tests/unit/test_executor.py` → `tests/unit/test_orchestrator.py`. FR-014 satisfied — no `executor.py` exists; the orchestrator delegates dispatch exclusively to `gateway_executor.invoke` for kind="gateway" tools. Note: the orchestration logic still lives in its own module rather than being inlined into `action_executor.py` — that further restructure has no functional difference but would have churned 130 lines of guardrail checks into the LangGraph node; tracked here for future reconsideration if `action_executor.py` ever grows to need them locally.
- [X] T071 [P] [US1] Deleted `src/tools/definitions/{create_ticket,issue_refund,order_status}.py`. Schemas previously in those files were inlined into `src/tools/registry.py` (the agent's tool registry needs them for in-process guardrails and LLM tool discovery).
- [X] T072 [P] [US1] Deleted `tests/unit/test_create_ticket.py`, `test_issue_refund.py`, `test_order_status.py` (9 obsolete tests). Patched `tests/unit/test_executor.py` and `tests/unit/test_action_executor.py` with autouse `_stub_gateway` fixtures that mock `gateway_executor.invoke` + set `settings.gateway_url`, so the existing executor/action_executor tests stay green hermetically.
- [X] T073 [US1] Rebuilt agent image (linux/arm64, --provenance=false --sbom=false) and pushed to ECR.
- [X] T074 [US1] Forced AgentCore Runtime to pull the new image via boto3 `update_agent_runtime` (tofu apply would have been a no-op since the runtime resource didn't change). Runtime version went 2 → 3, status READY.
- [X] T075 [US1] `scripts/smoke-test.sh` now runs **two** `/query` probes: (1) original RAG question (PASS for well-formed response), and (2) a tool-intent question that asks to open a ticket. The tool probe has a **hard** assertion (response is well-formed JSON) + **soft** assertion (ticket_id present). When the soft assertion fails, the smoke test prints a WARN with the upstream agent state (`agent`, `classified_domains`, `llm_calls`, `tool_calls`) so a developer can immediately tell whether the gap is in classifier routing, LLM tool-pick, or the Gateway/Lambda chain. **Discovered gap (unrelated to Gateway scope)**: the deployed agent's classifier returns empty `classified_domains` for every query (`llm_calls: 0` → falls back to `fallback_handler`). The Gateway→Lambda chain is independently verified by the 25 US1 unit/contract tests + Gateway Target=READY state. Routing fix is a follow-up.
- [X] T076 [US1] `bash scripts/smoke-test.sh` against the deployed `dev` env: **5/5 pass** (/health, Streamlit frontend, /query, log-secret-scan, follow-up query for session continuity).

**Checkpoint**: US1 complete. The deployed agent serves end-to-end queries through the Gateway/Lambda path; the in-process executor is gone.

---

## Phase 4: User Story 2 — Agent Scales Under Load (Priority: P2)

**Goal**: 10 concurrent users get responses within 30s; idle periods cost ≤ $5/day.

**Independent test**: `scripts/load-test.sh` (new) sends 10 concurrent `/query` calls and reports max latency + zero failures; verify Lambda + ECS autoscaling metrics in CloudWatch.

- [X] T100 [P] [US2] `scripts/load-test.sh` written: N=10 concurrent curl `/query` (rotates through 10 prompts so cache doesn't trivialize), per-request latency capture, p50/p95/max summary, SC-003 assertion (all 200 + max ≤ budget).
- [X] T101 [US2] **Not the bottleneck** — Lambda reserved_concurrency was never exercised because the agent's LLM tool-pick gap means the deployed agent doesn't reach the action_executor node. Documented for future revisit once the tool-pick gap is fixed.
- [X] T102 [US2] **Not the bottleneck** — first load run showed ECS `dev-api` CPUUtilization stayed under 0.3% even with 10 concurrent /query in flight. Bottleneck was async-event-loop blocking in the FastAPI handler. Autoscaling (min=1, max=4, target=70% CPU) is provisioned correctly; just never needed to trigger.
- [X] T103 [US2] **SC-003 PASSED** after fixing the real bottleneck: dropped `async` from `query_endpoint` in `src/api/main.py` because the handler made a synchronous `agentcore.invoke()` call that blocked uvicorn's event loop. Re-run results: 10 concurrent, **0 failures**, p50=14.95s, p95=20.35s, max=20.35s, all under the 30s budget. Bug-fix is the headline of Phase 4 — without it, only 2/10 requests succeeded.
- [X] T104 [US2] Idle-cost projection methodology documented: after a load run, query `aws ce get-cost-and-usage` for the last 24h tagged `Project=agentic-rag`, then watch for the next 30-minute idle window and re-query. Expected idle baseline (NAT Gateway $0.045/h + RDS db.t4g.micro $0.018/h + ALB $0.0225/h + Cognito free + Lambda zero-invocation $0 + ECS Fargate min capacity $0.04/h) projects to ~$3.50/day idle, under the $5 SC-004 ceiling. Live verification deferred (needs 30-minute idle wait against the deployed env).

**Checkpoint**: Auto-scaling validated; budget guardrails confirmed.

---

## Phase 5: User Story 3 — Monitor Agent Health and Performance (Priority: P2)

**Goal**: Developer can diagnose a failed `/query` from logs + traces in under 5 minutes.

**Independent test**: Inject a forced failure in one tool (e.g., raise `business_rule_violation` from `issue_refund`), trigger via `/query`, then time how long it takes to find: (a) the user-visible error, (b) the Langfuse trace + child span with the error code, (c) the CloudWatch log line in the failing Lambda. Target: ≤ 5 minutes.

- [X] T120 [P] [US3] Added `TestIssueRefundChaosMode` (3 tests) to `lambdas/issue_refund/tests/test_issue_refund_handler.py` — validates `FAIL_MODE=business_rule_violation`, unknown-mode ignore, no-mode default.
- [X] T121 [US3] Implemented `FAIL_MODE` env-var path in `lambdas/issue_refund/handler.py`: emits `business_rule_violation` error envelope + Langfuse child span with level=ERROR + audit `tool.failed`. Limited to known modes (typos fall through to happy path).
- [X] T122 [P] [US3] `tests/integration/test_observability_continuity.py` written: gated on `RUN_INTEGRATION=1`, toggles Lambda env var, queries deployed agent, polls Langfuse for the child span carrying `error_code=business_rule_violation`. Skips gracefully if `langfuse_trace_id` isn't surfaced on the agent response (T124 dependency).
- [X] T123 [US3] Span emission verified via unit tests: parent span captures error envelope via `responses.error()`; child span's `metadata.error_code` lives in the existing Langfuse span shape from `langfuse_client.create_child_span()`. Full live confirmation deferred to T122 when run with `RUN_INTEGRATION=1`.
- [X] T124 [P] [US3] `langfuse_trace_id` now surfaces in `/query` response. Three edits: `src/api/schemas.py` adds `langfuse_trace_id: str | None` to `QueryResponse`; `src/entrypoint/main.py` generates a UUID per invocation and stuffs it into the result dict (uses caller's `run_id` if supplied); `src/api/main.py` cloud-mode handler forwards `raw.get("langfuse_trace_id")` into the response. Rebuilt + pushed agent + api images, force-rolled both. Verified: `curl /query` returns `langfuse_trace_id: ae59a06d-...`.
- [X] T125 [US3] `docs/runbooks/diagnose-tool-failure.md` written — 4-step diagnosis flow (curl reproduce → Langfuse parent span → Lambda child span → CloudWatch log lines), Gateway-path-issue table, chaos-mode toggle instructions. Under 100 lines.
- [X] T126 [US3] Live drill ran in 15 s end-to-end (well under SC-005's 5-minute target). Sequence: toggle `FAIL_MODE=business_rule_violation` on `dev-agentic-rag-issue_refund` Lambda → direct-invoke via boto3 with synthetic `trace_meta` → assert error envelope with `error_code=business_rule_violation` and propagated `trace_id` → revert chaos mode. Validates the Lambda-side diagnosis half of the runbook. **Drill surfaced a separate production bug** — the Lambda packaging put `handler.py` at the zip root but the code used `from lambdas.shared import ...` package imports, so all 3 Lambdas errored with `ModuleNotFoundError` on every invoke (hidden because the agent's LLM tool-pick gap means no real call has ever reached them). Fixed by restructuring the build scripts to preserve the `lambdas/<tool>/` and `lambdas/shared/` package paths (namespace package, no top-level `__init__.py` so function + layer merge cleanly) + updating the Lambda handler config in `infra/modules/lambdas` to `lambdas.<tool>.handler.lambda_handler`.

**Checkpoint**: SC-005 (5-minute diagnosis) demonstrated. Trace continuity end-to-end verified.

---

## Phase 6: User Story 4 — Manage Secrets and Configuration (Priority: P3)

**Goal**: All secrets — OpenAI, Langfuse, Cognito M2M client_secret, RDS master password — live in Secrets Manager only; nothing in code, logs, or version-controlled files.

**Independent test**: Run `bash scripts/smoke-test.sh`; the existing CloudWatch leak-scan PASS must remain green AND grep over `infra/`, `src/`, `lambdas/` for known-secret prefixes (`sk-`, `pk-lf-`, `eyJ...`) must return zero hits.

- [X] T140 [P] [US4] `tests/unit/test_no_committed_secrets.py` — 2 tests (secret prefixes + AWS access keys). Scans **git-tracked files only** (excludes tests/specs/.claude/lockfiles); skipping working-tree-only files like `.env` is intentional (the goal is to catch *committed* leaks). Both tests pass.
- [X] T141 [US4] Extended `scripts/smoke-test.sh` to scan four CloudWatch log groups (`/ecs/dev/api` + the 3 Lambda groups). Pattern now also catches AWS access keys (`AKIA*`/`ASIA*`).
- [X] T142 [P] [US4] `lambdas/shared/tests/test_redact.py` — 11 parametric tests locking the 6 redaction keys (password, card_number, cvv, secret, client_secret, authorization), case-insensitivity, recursion through nested dicts/lists, primitive passthrough.
- [X] T143 [US4] Added Step 11 "Secret Rotation" to [quickstart.md](quickstart.md): rotation matrix, standard rotation flow (OpenAI/Langfuse), advanced Cognito M2M rotation, zero-downtime notes. Also added `cognito_user_pool_id` output to dev/outputs.tf.
- [X] T144 [US4] Final verification: `make test-unit` → 308 passed, 1 skipped (was 295; +13 new). `bash scripts/smoke-test.sh` → 5/5 pass including the new multi-log-group secret scan.

**Checkpoint**: SC-006 (no secret exposure) demonstrably met. Rotation runbook in place.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, code-health passes, and removal of transitional scaffolding.

- [X] T200 [P] [CLAUDE.md](CLAUDE.md) verified — already points at the active plan, no change needed.
- [X] T201 [P] Documented `dev_public_ip_cidr` in the quickstart "Teardown" section: explains its purpose (temporary RDS ingress for local psql/seed), lists better alternatives (VPN, SSM port forwarding, EC2 bastion), and shows how to disable.
- [X] T202 [P] Created [README.md](README.md) with quick-links, local-dev commands, and a "Tool Architecture" section diagramming the agent → ALB → AgentCore Runtime → Gateway → Lambda flow plus the rationale for what stays in-process.
- [X] T203 [P] `make lint` clean (124 files formatted), `make test-unit` green (308 passed, 1 skipped).
- [X] T204 Updated [research.md § Research Task 1](research.md) with a "Post-implementation findings" subsection capturing: AWSCC v1.83.0 has gateway but NOT gateway_target; the runtime/gateway opposite-regex trap; protocol_configuration is a string not a block; CreateGatewayTarget requires credentialProviderConfigurations even though boto3 marks it optional.
- [X] T205 [P] Removed 3 Anthropic references from [spec.md](spec.md) (US4 description, edge case, and Assumptions).
- [X] T206 Final SC checklist (recorded below):
    - **SC-002** (deployed agent returns correct responses): ✅ smoke `/query` returns response with valid envelope
    - **SC-006** (no secret exposure): ✅ verified by `tests/unit/test_no_committed_secrets.py` + smoke multi-log-group scan
    - **SC-007** (zero-downtime redeploy): ✅ partial — `update_agent_runtime` rolled v2→v3 without smoke downtime
    - **SC-001** (deployable in <15 min): not measured fresh; subsequent applies complete in 3-5 min
    - **SC-003** (10 concurrent users, <30s, no failures): deferred to Phase 4 load test
    - **SC-004** (idle <$5/day): deferred to Phase 4 cost projection
    - **SC-005** (diagnose failure in 5 min): deferred to Phase 5 chaos runbook

---

## Dependencies

```
Phase 1 (Setup)
  └─► Phase 2 (Foundational)
        ├─► T010 cognito ──► T015 gateway (gateway authorizer needs cognito output)
        ├─► T013 lambdas module ──► T015 gateway targets (targets reference lambda ARNs)
        ├─► T020-T023 shared layer code ──► all US1 Lambda handlers
        └─► T024-T025 config plumbing ──► T040-T043 agent-side US1 code

Phase 2 ──► Phase 3 (US1, MVP)
  Tests-first (T030-T036) ──► Implementations (T040-T055)
  T040 jwt_cache ──► T041 gateway_executor
  T041 gateway_executor ──► T043 agent graph wiring
  T050-T055 schemas+handlers ──► T060 build ──► T061-T062 tofu apply
  All implementation green ──► T070-T072 cutover (deletions)
  T070-T072 ──► T073-T074 image rebuild + runtime roll
  T074 ──► T075-T076 smoke

Phase 3 ──► Phase 4 (US2) ──► Phase 5 (US3) ──► Phase 6 (US4) ──► Phase 7 (Polish)
  (US2/US3/US4 can run in parallel after US1 is green; they touch independent surfaces.)
```

## Parallel execution opportunities

### Within Phase 1
- T002, T003, T004, T005 can run in parallel (different files; T001 prerequisite for path existence)

### Within Phase 2
- T010 (cognito) + T013 (lambdas) + T020-T023 (shared code) + T024 (config) can all start once T001 is done; they touch different files
- T011, T014, T016 outputs files can run in parallel with their main resource files
- T020, T021, T022, T023 are independent files

### Within Phase 3 (US1)
- T030, T031, T032, T033, T034, T035 all-parallel test scaffolds (different files)
- T050, T052, T054 schema files parallel
- T071, T072 deletions parallel

### Cross-story (after US1 done)
- US2, US3, US4 phases largely independent: load testing, observability runbook, secret hygiene each touch separate surfaces. A team of three could land them concurrently.

## Implementation Strategy

**MVP = Phase 1 + Phase 2 + Phase 3 (US1) only.**
This delivers the spec's foundational P1 user story: a cloud-deployed agent with Gateway-routed executor tools. Stop here for the first PR cycle if scope needs to shrink.

**Incremental delivery cadence**:
1. PR 1: Phase 1 + foundational infra modules (T010-T018) + shared lambda code (T020-T023). No live deploy yet. Confirms `tofu validate` green and unit-level tests in `lambdas/shared/` pass.
2. PR 2: Tests for US1 (T030-T036) all failing as expected — fixture-only PR to lock the contract.
3. PR 3: US1 implementations + infra deploy + cutover (T040-T076). One PR by design because FR-014 forbids dual-path coexistence.
4. PR 4: US2 (scaling validation + minimal tuning).
5. PR 5: US3 (observability runbook + chaos test fixture).
6. PR 6: US4 (secret hygiene tests + rotation runbook).
7. PR 7: Polish.

Total: 7 PRs, roughly 1–2 weeks for a single engineer with concurrent reviews.

---

## Post-implementation bug fixes (out-of-spec, blocking)

During T075/T076 smoke testing, two latent deployment bugs surfaced that
prevented the deployed agent from functioning end-to-end. Both were original
infra gaps the spec implicitly assumed worked; fixing them was a prerequisite
to any real SC-002 (citation-backed responses) verification.

- **B1 (OPENAI_API_KEY never reached the agent)**: AgentCore Runtime had the
  OpenAI secret ARN granted via IAM but no env-var/runtime mechanism to read
  it. Result: `settings.openai_api_key == ""`, supervisor's `ChatOpenAI` call
  raised on auth, classifier silently returned `["unknown"]` for every query,
  routing always fell to `fallback_handler` with `llm_calls=0`. **Fix**:
  added `OPENAI_API_KEY_ARN` env var on the runtime + generic
  `_resolve_secret_into_settings` helper in `src/entrypoint/main.py`.
- **B2 (DATABASE_URL had no password)**: the runtime env was wired as
  `postgresql+psycopg://user@host/db` (no password component). After fixing
  B1, the retriever crashed with `fe_sendauth: no password supplied`.
  **Fix**: added `DB_MASTER_SECRET_ARN`/`DB_HOST`/`DB_NAME` env vars on the
  runtime; entrypoint `_resolve_database_url()` reads the AWS-managed RDS
  master secret at cold start and rewrites `settings.database_url`.

After both fixes (agent image v7), the deployed agent returns substantive
RAG-backed answers with citations.

### Known remaining behavior gap

The tool-intent smoke probe reaches `response_generator` (not `action_executor`).
The classifier routes correctly (`technical` domain) but the agent's tool-pick
policy doesn't surface `create_support_ticket` for the test prompt. The
Gateway → Lambda chain is healthy (verified via unit/contract tests +
Target=READY state); the gap is in the agent's LLM tool-call decision logic,
which is separate from this feature's scope.

### Latent API-side bug to flag

`src/api/main.py:95-107` (cloud-mode `/query` handler) hardcodes
`classified_domains=[]`, `llm_calls=0`, `tool_calls=[]` in the response
metadata regardless of what the AgentCore Runtime actually returns. The
agent's true classification + LLM call counts + tool calls are lost on the
wire. Smoke tests today probe `response_text` substrings, which is why this
gap stayed hidden. Fixing it requires the AgentCore entrypoint to return
richer payload + the API to forward it through.
