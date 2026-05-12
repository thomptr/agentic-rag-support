# Research: AgentCore Gateway + Lambda Tool Refactor

**Feature**: 005-aws-agentcore-deployment (refactor scope)
**Date**: 2026-05-10

> The earlier deployment-only research (vector store choice, AgentCore Runtime
> deployment model, networking) is captured in this branch's git history.
> The artifact has been refreshed for the Gateway/Lambda refactor scope.

## Research Task 1: AWSCC schema for AgentCore Gateway and Targets

### Decision
Use `awscc_bedrockagentcore_gateway` with `authorizer_type = "CUSTOM_JWT"` and `protocol_type = "MCP"`; register Lambda backends as Gateway targets. Confirm the exact attribute names against the installed AWSCC v1.83.0 schema before writing the OpenTofu module — this avoids repeating the `agent_runtime` vs `runtime` naming bug we hit on the Runtime resource.

### Rationale
- The AWSCC provider ships these resources (`awscc_bedrockagentcore_gateway` was visible in the schema dump done while debugging the runtime).
- `CUSTOM_JWT` matches the Cognito M2M auth model selected in Q4.
- `MCP` is the agent's tool-call protocol of choice; the bedrock-agentcore SDK and the official MCP Python client both speak this.

### Alternatives considered
- **Direct Lambda invocation from the agent (no Gateway)**: Rejected — loses uniform tracing, doubles auth surface (the agent would need IAM perms on every Lambda), and the spec mandates Gateway (FR-012).
- **BYO MCP server on ECS/Fargate**: Rejected — reimplements what AgentCore Gateway already provides.

### Action items for Phase 1
- Verify `awscc_bedrockagentcore_gateway_target` schema shape before authoring `infra/modules/agentcore_gateway/main.tf`.

### Post-implementation findings (backfilled 2026-05-10)

What the AWSCC schema **actually** supported at v1.83.0 once we tried to apply:

- `awscc_bedrockagentcore_gateway` — **available**. Settable fields verified: `name`, `description`, `protocol_type`, `authorizer_type`, `authorizer_configuration` (nested with `custom_jwt_authorizer.{discovery_url, allowed_audience, allowed_clients}`), `role_arn`.
- `awscc_bedrockagentcore_gateway_target` — **NOT present**. There is no first-class target resource in this AWSCC version. Targets are registered out-of-band via `scripts/register-gateway-targets.sh` (boto3 + `bedrock-agentcore-control` client). When AWSCC ships the resource, migrate the script's logic into the `agentcore_gateway` module and import the existing targets into state.
- Two name regex traps surfaced during the apply:
  - **Runtime** name must match `^[a-zA-Z][a-zA-Z0-9_]*$` — no dashes (uses underscores).
  - **Gateway** name must match `^([0-9a-zA-Z][-]?){1,100}$` — no underscores (uses dashes).
  These are opposite constraints on sibling resources; document this in any future module to save a re-apply cycle.
- The `protocol_configuration` field on `awscc_bedrockagentcore_runtime` is a plain string in the AWSCC schema (e.g. `"HTTP"`), not a nested block as documentation initially suggested.
- `CreateGatewayTarget` (the boto3 control-plane call) requires `credentialProviderConfigurations` even though the input shape marks it optional. For Lambda targets backed by the Gateway's own IAM role, pass `[{credentialProviderType: "GATEWAY_IAM_ROLE"}]`.

## Research Task 2: Cognito M2M configuration for the Gateway authorizer

### Decision
- One Cognito **User Pool** dedicated to AgentCore service-to-service auth.
- One **Resource Server** (e.g., `agentic-rag-tools`) defining a scope (`gateway.invoke`).
- One **App Client** with `client_credentials` OAuth2 flow enabled, the scope granted, and no public-facing settings.
- App client `client_secret` stored in Secrets Manager and read by the AgentCore Runtime at startup.
- Token endpoint: `https://<domain>.auth.<region>.amazoncognito.com/oauth2/token`.

### Rationale
- Cognito M2M is the AWS-managed JWT issuer pattern AgentCore Gateway aligns to. No external IdP burden.
- Resource server + scope gives a clear authorization claim the Gateway can check.
- Hosted UI is unnecessary for M2M; only the token endpoint is consumed.

### Alternatives considered
- **External IdP (Auth0, Okta)**: Rejected (Q4 → A).
- **Self-signed JWT with a custom key**: Rejected — Gateway's CUSTOM_JWT trusts a discovery document; managing rotation ourselves is operational toil for no benefit over Cognito.

### Action items
- Add `cognito_token_url` and `cognito_client_id` to `src/config.py` and the AgentCore Runtime env.
- Token caching: in-memory dict keyed by `(client_id, scope)`, refresh when `exp - now < 60s`.

## Research Task 3: Lambda packaging — zip vs container, ARM64

### Decision
**Zip packaging** with a thin shared **Lambda Layer** for cross-cutting concerns (Langfuse SDK init, tracing helper, audit emitter). Per-tool deps (typically just `pydantic`) ship in the function bundle.

### Rationale
- Cold-start target <3 s p95. Zip cold-starts 200–800 ms faster than container images at these sizes.
- The three executor tools (`create_ticket`, `issue_refund`, `order_status`) are mocks with tiny logic — no OS-level deps required.
- Layer carries Langfuse SDK (~10 MB) and aws-lambda-powertools (~5 MB) so each function bundle stays well under the 50 MB direct-upload limit.
- ARM64 packaging matches the AgentCore Runtime + ECS ARM64 baseline.

### Alternatives considered
- **Container images**: Rejected for cold-start. Revisit if a future tool needs native deps too large for a Layer.
- **Per-tool deps inlined (no Layer)**: Rejected — duplicates ~15 MB across every Lambda and slows cold starts.

## Research Task 4: Trace-context propagation from agent → Gateway → Lambda

### Decision
- Agent creates a Langfuse **parent span** per tool call, captures `trace_id` and `span_id`, and includes them as **fields in the tool-call payload** (not headers).
- Lambda handler extracts `trace_id` and `parent_span_id` from its input event and creates a Langfuse **child span** with those fields set as `traceId` / `parentObservationId`.
- Each Lambda initializes Langfuse once at module top-level (cold-start cost paid once per container lifetime). Credentials read from Secrets Manager at cold start.

### Rationale
- MCP tool-call schemas treat the payload as the contract; relying on Gateway to forward arbitrary HTTP headers is fragile and undocumented. Putting `trace_id` in the payload is portable and explicit.
- Lazy SDK init avoids paying Langfuse-network cost on every invocation.

### Alternatives considered
- **HTTP header propagation (W3C traceparent)**: Rejected pending confirmation that AgentCore Gateway forwards arbitrary headers verbatim to Lambda targets. Easy future migration if that's later confirmed.
- **Agent-side span only**: Rejected (Q5 → B). Loses Lambda-internal observability.

### Action items
- Define `trace_meta` field on the Lambda input schema (`contracts/tool-lambda.md`). All three Lambdas accept it.

## Research Task 5: Hard-cutover impact on existing tests

### Decision
- Delete `tests/unit/test_executor.py` and per-tool unit tests under `tests/unit/tools/`. Replace with:
  - `tests/unit/test_gateway_executor.py` — mocks the MCP client, asserts agent-side spans + JWT handling.
  - `lambdas/<tool>/tests/test_handler.py` — unit-tests each Lambda handler with a stub Langfuse client.
- Add `tests/integration/test_gateway_e2e.py` — exercises agent → Gateway → Lambda round-trip against deployed `dev` (skip in CI unless `RUN_INTEGRATION=1`).

### Rationale
- Constitution Principle III requires failing tests before implementation. Replacing the test files alongside the code change keeps coverage continuous.
- Splitting unit (per-Lambda) from integration (cross-service) lets the unit tier run fast in CI without AWS.

### Alternatives considered
- **Keep existing tests as-is, run them against a local MCP-mock Gateway**: Rejected — adds a parallel test path that drifts from the deployed contract.

## Research Task 6: Approval-workflow ordering with Gateway tools

### Decision
The agent's LangGraph node order is unchanged: `guardrails` → `approval` → `tool_dispatch`. Only the `tool_dispatch` node changes — it calls `gateway_executor.invoke(name, args, trace_meta)` instead of `execute_tool(...)`. Approval state remains entirely in-process. Lambdas never query approval state.

### Rationale
- Q1 (only executor migrates) + Q3 (hard cutover) imply the approval gate stays inside the agent. Moving it would defeat the migration scope.
- Stateless Lambdas align with per-tool least-privilege — no DynamoDB or RDS for approval state.

### Alternatives considered
- **Lambda-side approval check (via DynamoDB)**: Rejected — adds storage dependency to every Lambda and complicates the in-process approval workflow that already works.

## Research Task 7: Gateway target resource mapping for the three tools

### Decision
- One `awscc_bedrockagentcore_gateway_target` per tool. Target name = tool name (`create_ticket`, `issue_refund`, `order_status`).
- The tool's MCP tool definition (name, description, input schema) is supplied to the target during creation; it surfaces to the agent through Gateway's MCP discovery.
- Lambda ARN reference uses `aws_lambda_function.<tool_name>.arn` from `infra/modules/lambdas`.

### Rationale
- 1:1 mapping keeps OpenTofu output predictable.
- MCP discovery means `src/tools/registry.py` no longer hardcodes executor tools — the agent learns them from the Gateway. In-process tools (approval, audit, guardrails) remain a fixed list.

### Action items
- Replace static executor entries in `src/tools/registry.py` with a Gateway-backed discovery call at cold start.
