# API Contract: AWS AgentCore Deployment

**Feature**: 005-aws-agentcore-deployment
**Date**: 2026-05-09

## Overview

This feature introduces one new internal interface (FastAPI → AgentCore Runtime) and modifies the deployment context of existing interfaces. The public-facing API contract (FastAPI endpoints) remains unchanged from the user's perspective.

## Interface 1: AgentCore Runtime Invocation (NEW)

**Type**: Internal service-to-service HTTP
**Direction**: FastAPI API → AgentCore Runtime
**Protocol**: HTTP POST to AgentCore Runtime endpoint

### Request

```
POST https://{agentcore-endpoint}/invocations
Content-Type: application/json
Authorization: AWS Signature V4

{
  "prompt": "string",           // User's query text
  "session_id": "string",       // Session identifier for conversation context
  "guardrails_enabled": true,   // Whether tool guardrails are active
  "model_override": "string"    // Optional model selection override
}
```

### Response

```json
{
  "result": {
    "query_id": "string",
    "response_text": "string",
    "agent": "string",
    "routing_rationale": "string",
    "citations": [
      {
        "content": "string",
        "domain": "string",
        "source": "string",
        "score": 0.95,
        "doc_id": "string",
        "chunk_text": "string",
        "title": "string",
        "source_file": "string"
      }
    ],
    "metadata": {
      "classified_domain": "string",
      "classified_domains": ["string"],
      "run_id": "string",
      "total_latency_ms": 0,
      "llm_calls": 0,
      "retrieval_calls": 0,
      "retrieval_attempts": 0,
      "documents_retrieved": 0,
      "documents_after_dedup": 0,
      "retrieval_confidence": 0.0
    },
    "tool_calls": [
      {
        "tool_name": "string",
        "status": "string",
        "result": "string",
        "error": "string",
        "block_reason": "string",
        "approval_id": "string"
      }
    ],
    "pending_approvals": [
      {
        "approval_id": "string",
        "tool_name": "string",
        "arguments": {}
      }
    ]
  }
}
```

### Error Responses

| Status | Meaning |
|--------|---------|
| 200 | Successful invocation |
| 429 | Rate limited (exceeds 25 TPS per agent) |
| 500 | Agent runtime error |
| 503 | Service unavailable (scaling, cold start) |

### Authentication

AgentCore invocations use AWS IAM Signature V4. The ECS task role must have `bedrock-agentcore:InvokeAgentRuntime` permission on the agent runtime ARN.

---

## Interface 2: AgentCore Service Contract (NEW)

**Type**: Container service contract
**Direction**: AgentCore Runtime → Agent container
**Protocol**: HTTP on port 8080

### Health Check

```
GET /ping
Response: 200 OK (healthy) or 200 "HealthyBusy" (active session)
```

### Invocation

```
POST /invocations
Content-Type: application/json

{
  "prompt": "string",
  "session_id": "string",
  "guardrails_enabled": true,
  "model_override": "string"
}
```

The `BedrockAgentCoreApp` SDK handles routing to the `@app.entrypoint` function. The entry point receives the parsed JSON as `payload` and an AgentCore `context` object.

---

## Interface 3: Public API (UNCHANGED)

The existing FastAPI endpoints remain unchanged from the consumer's perspective:

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/query` | Submit a support query |
| GET | `/approvals` | List pending tool approvals |
| POST | `/approvals/{id}/approve` | Approve a tool action |
| POST | `/approvals/{id}/reject` | Reject a tool action |
| GET | `/health` | System health check |

**Internal change**: The `/query` endpoint now calls AgentCore Runtime (via `agentcore_client.py`) instead of invoking the graph directly. The request/response schemas (`QueryRequest`, `QueryResponse`) are unchanged.

---

## Interface 4: Frontend → API (UNCHANGED)

The Streamlit frontend connects to the FastAPI API via HTTP. The only change is the `API_URL` environment variable, which points to the ALB endpoint instead of `localhost:8000`.

**Configuration**:
```
API_URL=http://{alb-dns-name}:80  (internal, via ALB)
```

---

## Interface 5: Database Connection (UNCHANGED)

The application connects to PostgreSQL using the same `DATABASE_URL` format:

```
postgresql+psycopg://{user}:{password}@{rds-endpoint}:5432/agentic_rag
```

The only change is the hostname (RDS endpoint instead of `localhost`). The `langchain_postgres.PGVector` client, collection name (`support_kb`), and all queries are unchanged.

---

## IAM Policy Requirements

### ECS Task Execution Role

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/ecs/dev/*"
    },
    {
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:*:*:secret:dev/agentic-rag/*"
    }
  ]
}
```

### ECS Task Role (API Service)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "bedrock-agentcore:InvokeAgentRuntime",
      "Resource": "arn:aws:bedrock-agentcore:*:*:runtime/agentic-rag-agent/*"
    }
  ]
}
```

### AgentCore Runtime Role

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:*:*:secret:dev/agentic-rag/*"
    }
  ]
}
```
