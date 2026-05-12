# Implementation Plan: AWS AgentCore Deployment + Gateway/Lambda Tool Refactor

**Branch**: `005-aws-agentcore-deployment` | **Date**: 2026-05-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification at `specs/005-aws-agentcore-deployment/spec.md`

## Summary

Refactor the agent's three executor action tools (`create_ticket`, `issue_refund`, `order_status`) to be hosted as independent AWS Lambda functions and exposed to the agent through an AWS AgentCore Tool Gateway. The agent (running in AgentCore Runtime) authenticates to the Gateway with a Cognito User Pool M2M OAuth2 client_credentials JWT; the Gateway routes each tool call to its dedicated Lambda target. Approval, audit, and guardrails remain in-process inside the agent runtime. The refactor is a hard cutover: the existing in-process executor is deleted in the same release.

The AWS deployment infrastructure (VPC, RDS, ECS, AgentCore Runtime, secrets) is the substrate this refactor lands on; that work is already partially provisioned on this branch.

## Technical Context

**Language/Version**: Python 3.11 (agent + Lambdas) | OpenTofu 1.8+ (infra)
**Primary Dependencies**: LangGraph 0.4+, FastAPI 0.115+, Streamlit 1.40+, bedrock-agentcore SDK, MCP client SDK (`mcp` Python package), Langfuse SDK 2.x, langchain-postgres, psycopg 3.2+, botocore (SigV4), AWS Powertools for Lambda (Python)
**Storage**: PostgreSQL 16 + pgVector on RDS; Secrets Manager for API keys and Cognito credentials; Cognito User Pool for JWT issuance
**Testing**: pytest + pytest-asyncio for agent and Lambda handlers; contract tests for the Lambda request/response schema; `tofu validate` + `tofu plan` for infra; `scripts/smoke-test.sh` end-to-end after deploy
**Target Platform**: AWS us-east-1 — AgentCore Runtime (ARM64) + AgentCore Tool Gateway + Lambda (ARM64) + ECS Fargate (ARM64) + RDS + Cognito
**Project Type**: Multi-service cloud deployment with refactored remote-tool architecture
**Performance Goals**: 10 concurrent users; agent-to-tool round-trip <2s p95 (warm); Lambda cold start <3s p95
**Constraints**: All compute on ARM64; AgentCore in supported AZs only (use1-az1/2/4); JWT-only auth to the Gateway; per-tool least-privilege IAM; Langfuse trace continuity from agent → Lambda (no broken parent/child links)
**Scale/Scope**: 3 executor tools migrate now; pattern extensible to additional tools later. POC, single environment (`dev`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. RAG-First | PASS | Refactor only touches tool execution; retrieval pipeline is unaffected. |
| II. Agentic Autonomy | PASS | The agent still decides when to call tools. Tool *boundary* moves from in-process Python to Gateway-routed Lambda; the agent's tool-use loop is preserved. |
| III. Test-First (NON-NEGOTIABLE) | PASS (commitment) | Contract tests for Lambda payloads MUST land before Lambda implementations. Agent-side Gateway client MUST have failing tests before its implementation. Captured in tasks. |
| IV. Observability | PASS | FR-016 mandates Langfuse parent span in the agent and Langfuse child spans inside every Lambda, linked via propagated `trace_id`. CloudWatch structured logs in every Lambda. |
| V. Simplicity (POC) | **JUSTIFIED COMPLEXITY** | Adding Gateway + Cognito + per-tool Lambdas increases surface area beyond an in-process executor. Spec FR-012 through FR-016 explicitly mandates this; trade-off accepted as part of the AgentCore deployment story. See Complexity Tracking below. |

**Result**: All gates pass. Principle V complexity is documented and justified.

## Project Structure

### Documentation (this feature)

```text
specs/005-aws-agentcore-deployment/
├── plan.md              # This file
├── research.md          # Phase 0 output — open decisions resolved
├── data-model.md        # Phase 1 output — entities + state transitions for the refactor
├── quickstart.md        # Phase 1 output — deploy + smoke-test walkthrough (already exists; refreshed)
├── contracts/
│   ├── api.md           # Existing FastAPI contract (no change)
│   └── tool-lambda.md   # NEW — Lambda invocation contract (Gateway → Lambda → response)
├── checklists/
│   └── requirements.md  # Existing
├── spec.md              # Feature spec (clarified for this refactor)
└── tasks.md             # Phase 2 output — created by /speckit-tasks
```

### Source Code (repository root)

```text
src/
├── api/                 # FastAPI — no change in this phase
├── agent/ (if present)  # LangGraph workflow — UPDATED to call Gateway instead of in-process executor
├── entrypoint/          # AgentCore Runtime entry — UPDATED to wire Gateway client + token cache
├── tools/
│   ├── approval.py      # KEPT in-process
│   ├── audit.py         # KEPT in-process
│   ├── guardrails.py    # KEPT in-process
│   ├── registry.py      # MODIFIED — registry now records MCP-tool names, not Python callables
│   ├── executor.py      # DELETED — replaced by gateway_executor.py (single-source replacement)
│   ├── gateway_executor.py  # NEW — calls the AgentCore Tool Gateway via MCP, handles JWT auth + tracing
│   └── definitions/
│       ├── create_ticket.py    # DELETED (logic moves to lambdas/create_ticket/)
│       ├── issue_refund.py     # DELETED
│       └── order_status.py     # DELETED
├── config.py            # UPDATED — adds gateway_url, cognito_client_id/secret, cognito_token_url
└── rag/                 # No change

lambdas/                 # NEW top-level directory — one subfolder per executor tool
├── create_ticket/
│   ├── handler.py
│   ├── schema.py        # Pydantic models for input/output (mirrors src/tools/definitions/create_ticket.py)
│   ├── requirements.txt # langfuse, aws-lambda-powertools, pydantic, structlog
│   └── tests/
│       └── test_handler.py
├── issue_refund/
│   └── ... (same shape)
├── order_status/
│   └── ... (same shape)
└── shared/              # Common code packaged as a Lambda Layer
    ├── langfuse_client.py    # Cold-start init + child-span helper
    ├── audit_emitter.py      # Same shape as in-process audit, but logs to stdout for CloudWatch
    └── tracing.py            # trace_id extraction from Gateway-supplied headers

infra/
├── bootstrap/                # State + KMS — no change
├── modules/
│   ├── networking/           # MODIFIED — already updated for AZ + dev IP rules
│   ├── database/             # MODIFIED — already updated for subnet group + public access toggle
│   ├── ecr/                  # MODIFIED — adds repos for Lambda images (if container-based)
│   ├── ecs/                  # MODIFIED — drops the in-process executor permissions; gains MCP endpoint env vars
│   ├── secrets/              # MODIFIED — adds langfuse_keys grant to Lambda exec roles
│   ├── agentcore/            # MODIFIED — adds environment vars for Gateway URL + Cognito M2M
│   ├── cognito/              # NEW — user pool + resource server + M2M app client + Secrets Manager binding
│   ├── lambdas/              # NEW — one aws_lambda_function per executor tool; per-tool IAM role; Lambda Layer for shared code
│   └── agentcore_gateway/    # NEW — awscc_bedrockagentcore_gateway + targets (one per Lambda) + authorizer_configuration referencing Cognito
└── environments/dev/         # MODIFIED — wires new modules

docker/                  # Existing Dockerfile.agent / .api / .frontend — no change
scripts/
├── deploy.sh            # MODIFIED — packages Lambdas, registers Gateway targets
└── smoke-test.sh        # MODIFIED — adds a tool-call assertion that verifies Gateway/Lambda path
```

**Structure Decision**: Hybrid in-tree layout — agent and Lambda source coexist in the repo with shared types. Lambdas use a small `shared/` Layer for Langfuse + tracing helpers so each Lambda's bundle stays small and cold-start fast. OpenTofu module per concern (cognito, lambdas, agentcore_gateway) keeps the existing module conventions.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| New `cognito/` OpenTofu module + User Pool + M2M client | FR-015 requires JWT authentication to the Gateway. Cognito is the AWS-managed JWT issuer that integrates cleanly with AgentCore Gateway's `CUSTOM_JWT` authorizer. | Skipping authorizer was rejected — Gateway requires `authorizer_type`. Bringing an external IdP was rejected by the user (Q4 → A). |
| `agentcore_gateway/` module + per-tool target | FR-012 mandates Gateway-fronted tools. | An open Gateway (no authorizer) was rejected (Q4 → A). Calling Lambdas directly from the agent without a Gateway was rejected because it loses MCP-style tool discovery + uniform tracing and shifts auth burden onto each Lambda. |
| Three Lambda functions (one per tool) + per-Lambda IAM role | FR-013 mandates per-tool Lambdas with least-privilege IAM. | Multiplexed Lambda was rejected (Q2 → A). Justified by simpler IAM auditing and independent rollback. |
| Langfuse SDK in every Lambda + Secrets Manager grant | FR-016 mandates full trace continuity, not just agent-side spans. | Agent-side-only spans was rejected (Q5 → B). The cost — one cold-start SDK init and Secrets Manager read — was accepted to preserve trace fidelity matching SC-005's 5-minute debug target. |
| `gateway_executor.py` replacing `executor.py` (hard cutover) | FR-014 forbids permanent dual-path. | Coexistence rejected (Q3 → A) to avoid carrying two execution paths in the codebase. |

## Notes & Open Risks

- **AgentCore Gateway resource schema verification**: Phase 0 must confirm the AWSCC schema for `awscc_bedrockagentcore_gateway` and `..._target` accepts the JWT/Cognito configuration shape we plan to write. The runtime resource already revealed a name/attribute mismatch (`runtime` vs `agent_runtime`); Gateway may have similar quirks.
- **JWT caching**: The agent must cache the M2M JWT and refresh ~60s before expiry. Without this, every tool call costs a Cognito round-trip. Phase 1 design captures the cache mechanism.
- **Trace context propagation**: The Gateway → Lambda call must carry `trace_id` and `parent_span_id`. If AgentCore Gateway doesn't forward custom headers verbatim, we encode them in the tool-call payload instead. Phase 0 research item.
- **Approval workflow boundary**: Approval is still in-process. Confirm in Phase 1 data-model that the agent calls `approval` *before* dispatching to the Gateway and never asks the Lambda for approval state.
