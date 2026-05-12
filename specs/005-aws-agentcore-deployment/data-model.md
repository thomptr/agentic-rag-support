# Data Model: AgentCore Gateway + Lambda Tool Refactor

**Feature**: 005-aws-agentcore-deployment (refactor scope)
**Date**: 2026-05-10

This document covers entities introduced or significantly changed by the Gateway/Lambda refactor. The existing deployment entities (VPC, RDS, ECS, AgentCore Runtime, Secrets) are unchanged at the data-model level except where noted.

## Entities

### AgentCore Tool Gateway
The managed proxy that exposes executor tools to the agent over MCP.

| Field | Type | Notes |
|---|---|---|
| name | string | `dev-agentic-rag-tools` |
| protocol_type | enum | `MCP` |
| authorizer_type | enum | `CUSTOM_JWT` |
| authorizer_configuration.discovery_url | URL | `https://cognito-idp.<region>.amazonaws.com/<user-pool-id>/.well-known/openid-configuration` |
| authorizer_configuration.allowed_audience | list[string] | The Cognito resource server scope (`agentic-rag-tools/gateway.invoke`) |
| role_arn | ARN | IAM role the Gateway assumes when invoking Lambda targets |
| gateway_url | URL (computed) | The endpoint the agent uses for MCP discovery + invocation |
| gateway_arn | ARN (computed) | Used for IAM grants on the agent runtime role |

**Lifecycle**: created once with `tofu apply`. Updates are in-place except for `authorizer_type` (replacement).

### Gateway Target (one per tool)
Binds a Gateway tool name to a Lambda ARN and an MCP tool schema.

| Field | Type | Notes |
|---|---|---|
| gateway_identifier | string (FK) | Reference to `AgentCore Tool Gateway` |
| target_name | string | Equals the tool name: `create_ticket` / `issue_refund` / `order_status` |
| target_type | enum | `LAMBDA` |
| lambda_arn | ARN | Output of `aws_lambda_function.<tool>` |
| tool_definition.name | string | MCP tool name; matches `target_name` |
| tool_definition.description | string | Surface text the agent's LLM uses to decide when to call this tool |
| tool_definition.input_schema | JSON Schema | Generated from the Pydantic `*Input` model in `lambdas/<tool>/schema.py` |
| tool_definition.output_schema | JSON Schema | Generated from the Pydantic `*Output` model |

**State transitions**: Target is `ACTIVE` when its Lambda is reachable and the schema validates. If a Lambda is deleted out-of-band, the target transitions to `FAILED` and Gateway returns a 502-class error to the agent for that tool.

### Executor Tool Lambda
A stateless function hosting one tool.

| Field | Type | Notes |
|---|---|---|
| function_name | string | `dev-agentic-rag-<tool>` |
| runtime | enum | `python3.11` |
| architectures | enum | `[arm64]` |
| handler | string | `handler.lambda_handler` |
| memory_size | int | 256 MB (start; tune per tool) |
| timeout | seconds | 15 (well within agent's per-tool budget) |
| role_arn | ARN | Per-tool IAM execution role |
| layers | list[ARN] | `[<shared-layer-arn>]` (Langfuse + Powertools + tracing) |
| environment_variables | map | `LANGFUSE_HOST`, `LANGFUSE_SECRET_REF`, `TOOL_NAME`, `LOG_LEVEL` |
| reserved_concurrency | int | Unset for POC; rely on default account concurrency |

**IAM role permissions (per-tool)**:
- `logs:CreateLogStream`, `logs:PutLogEvents` on the tool's CloudWatch log group only
- `secretsmanager:GetSecretValue` on `dev/agentic-rag/langfuse-*` only
- Tool-specific permissions added per business need (e.g., `dynamodb:PutItem` if a future tool writes to a DDB table)

### Cognito User Pool (Service-to-Service)
JWT issuer for the agent → Gateway path.

| Field | Type | Notes |
|---|---|---|
| pool_name | string | `dev-agentic-rag-svc` |
| domain | string | `dev-agentic-rag-svc.auth.<region>.amazoncognito.com` |
| resource_servers[0].identifier | string | `agentic-rag-tools` |
| resource_servers[0].scopes | list[{name, description}] | `[{name: "gateway.invoke", description: "Invoke executor tools via Gateway"}]` |
| app_clients[0].name | string | `agent-runtime` |
| app_clients[0].generate_secret | bool | `true` (M2M) |
| app_clients[0].allowed_oauth_flows | list | `["client_credentials"]` |
| app_clients[0].allowed_oauth_scopes | list | `["agentic-rag-tools/gateway.invoke"]` |
| app_clients[0].client_secret_arn | ARN | Stored in Secrets Manager — read by AgentCore Runtime at startup |

### Tool Invocation (transient)
The payload shape that flows agent → Gateway → Lambda → Gateway → agent. Not stored; documented here so both sides agree on the contract. Detailed schema in [contracts/tool-lambda.md](contracts/tool-lambda.md).

| Field | Type | Origin | Notes |
|---|---|---|---|
| tool_name | string | agent | MCP tool name |
| parameters | object | agent | Validated by Gateway against the Pydantic-derived JSON Schema |
| trace_meta.trace_id | UUID | agent | Langfuse trace ID — propagated end-to-end |
| trace_meta.parent_span_id | UUID | agent | Langfuse span ID of the agent's tool-dispatch span |
| trace_meta.session_id | UUID | agent | The user's conversation session ID (for log correlation) |
| trace_meta.run_id | UUID | agent | The current agent run ID |

## Relationships

```
Cognito User Pool ─┐
                   │ (validates JWT for)
                   ▼
        AgentCore Tool Gateway ──── (forwards to) ──── Gateway Target ──── (invokes) ──── Executor Tool Lambda
                ▲                                                                                │
                │ (tool calls via MCP, with JWT)                                                  │
                │                                                                                ▼
        AgentCore Runtime                                                                Langfuse (parent + child spans)
        (the agent process)
```

- A Gateway has 0..N Targets. We deploy exactly 3 for the POC.
- A Target has exactly 1 Lambda. (1:1 — never multiplexed, per FR-013.)
- A Lambda is referenced by exactly 1 Target. Lifetime is tied to the Target's lifetime.
- One Cognito User Pool serves all Gateways in this account/environment.
- The AgentCore Runtime holds **one** active JWT at a time per scope; in-memory cache, no persistence.

## Validation Rules

- Every Target's `tool_definition.input_schema` MUST match the Pydantic `*Input` model in the corresponding Lambda's `schema.py` byte-for-byte (validated by a contract test in `lambdas/<tool>/tests/test_handler.py`).
- Every Lambda input MUST include a `trace_meta` object with non-empty `trace_id` and `parent_span_id`. Missing trace_meta → Lambda returns a `400` with `error_code: "missing_trace_context"`.
- Lambda timeout (15 s) MUST be strictly less than the agent's per-tool dispatch deadline (Q: assume 25 s default — confirm in tasks). A Lambda timing out manifests at the agent as a Gateway 504 with `tool_name` echoed back.
- Gateway authorizer audience MUST include `agentic-rag-tools/gateway.invoke`. Mismatch → 401 to the agent.

## State Transitions

### Cognito JWT cache (in-agent)
```
  ┌──────────┐    request token    ┌────────────┐
  │  EMPTY   │ ─────────────────▶  │  FRESH     │
  └──────────┘                     └─────┬──────┘
                                          │ exp - now < 60s
                                          ▼
                                    ┌────────────┐
                                    │  STALE     │  ──── refresh ────▶ FRESH
                                    └────────────┘
```

### Tool-call flow
1. Agent enters `tool_dispatch` node.
2. Agent ensures cached JWT is FRESH (refreshes if STALE/EMPTY).
3. Agent creates Langfuse parent span.
4. Agent calls Gateway via MCP with `Authorization: Bearer <JWT>` and payload `{tool_name, parameters, trace_meta}`.
5. Gateway validates JWT, looks up Target, invokes Lambda.
6. Lambda runs, creates Langfuse child span, returns `{result, error?}`.
7. Gateway returns Lambda result to agent.
8. Agent closes parent span with outcome and resumes graph.

Failure paths:
- JWT invalid → agent receives 401 → caches as EMPTY → refresh → retry once → on second failure, fail the tool call (agent records audit event `tool.gateway.auth_failed`).
- Lambda timeout → agent receives 504 → fail the tool call (no retry — could be partially executed; safe default for POC).
- Lambda 5xx → retry once with exponential backoff, then fail.
