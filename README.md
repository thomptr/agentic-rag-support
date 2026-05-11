# Agentic RAG Support

POC agent that answers customer support questions via RAG over a private knowledge base, takes actions (ticket / refund / order lookup) through tool calls, and runs end-to-end on AWS.

## Quick links

- **Spec & plan**: [specs/005-aws-agentcore-deployment/](specs/005-aws-agentcore-deployment/)
- **Constitution**: [.specify/memory/constitution.md](.specify/memory/constitution.md)
- **Deployment guide**: [specs/005-aws-agentcore-deployment/quickstart.md](specs/005-aws-agentcore-deployment/quickstart.md)

## Local development

```bash
# One-time setup
uv venv && source .venv/bin/activate
uv pip install -e .

# Local services
make up       # starts PostgreSQL via docker compose
make seed     # ingests the knowledge base
make run      # FastAPI on :8000

# Tests
make lint
make test-unit
```

## Tool Architecture

The agent's executor action tools (`create_ticket`, `issue_refund`, `order_status`) are **remote Lambda functions** routed through an **AWS AgentCore Tool Gateway**, while approval, audit, and guardrails stay in-process inside the AgentCore Runtime container.

```text
User → ALB → FastAPI → AgentCore Runtime (LangGraph)
                              │
                              │ guardrails → approval → tool_dispatch
                              ▼
                         gateway_executor.invoke()
                              │
                              │ JWT (Cognito M2M) + MCP over HTTPS
                              ▼
                    AgentCore Tool Gateway
                              │
                              │ Gateway IAM role + lambda:InvokeFunction
                              ▼
                   Lambda (one per tool, ARM64)
                              │
                              │ Langfuse child span (linked to agent trace)
                              ▼
                         tool result envelope
```

**Why this split**:
- **Gateway tools** isolate per-tool IAM, make each tool independently versionable and language-agnostic, and surface uniform observability via the Gateway's request log + Langfuse trace continuity.
- **In-process framework concerns** (approval state machine, audit emitter, guardrail checks) stay tight against the agent graph where they need low-latency access to shared session state.

The dispatch contract is documented in [specs/005-aws-agentcore-deployment/contracts/tool-lambda.md](specs/005-aws-agentcore-deployment/contracts/tool-lambda.md).

## Layout

```
src/             # Agent + API + frontend code (deployed to AgentCore Runtime + ECS)
lambdas/         # Per-tool Lambda handlers + shared layer (deployed to AWS Lambda)
infra/           # OpenTofu modules (networking, RDS, ECR, ECS, Cognito, Lambdas, Gateway, AgentCore)
scripts/         # build-lambda*.sh, register-gateway-targets.sh, smoke-test.sh, deploy.sh
specs/           # Specifications, plans, tasks, design artifacts (speckit format)
tests/           # Unit + integration + eval tests for src/
```
