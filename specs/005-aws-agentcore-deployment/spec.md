# Feature Specification: AWS AgentCore Deployment

**Feature Branch**: `005-aws-agentcore-deployment`  
**Created**: 2026-05-09  
**Status**: Draft  
**Input**: User description: "Create AWS AgentCore deployment."

## Clarifications

### Session 2026-05-10

- Q: When refactoring tools to AgentCore Gateway + Lambda, which tools migrate? → A: Only the executor action tools. Approval, audit, and guardrails stay in-process as framework concerns co-located with the agent.
- Q: Lambda packaging granularity for executor tools? → A: One Lambda per tool — separate function, separate IAM role, separate deploy artifact.
- Q: Migration strategy from in-process executor to Gateway+Lambda? → A: Hard cutover — delete the in-process executor and route all executor calls through Gateway in a single change.
- Q: How does the AgentCore Runtime authenticate to the Gateway? → A: Cognito User Pool M2M — agent obtains OAuth2 client_credentials JWT and presents it to the Gateway, which validates via CUSTOM_JWT authorizer.
- Q: Observability strategy for Lambda-hosted tools? → A: Full Langfuse trace continuity — agent emits parent span, each Lambda initializes the Langfuse SDK and emits child spans linked via propagated trace_id; structured CloudWatch logs in addition.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Deploy Agent to Cloud (Priority: P1)

A developer deploys the agentic RAG support system to AWS so that the agent is accessible from anywhere, not just a local development machine. The developer triggers a deployment and the full system — agent, API, database, and frontend — becomes available at a cloud-hosted endpoint.

**Why this priority**: Without a working cloud deployment, the agent cannot serve real users or be evaluated in a production-like environment. This is the foundational capability that all other stories depend on.

**Independent Test**: Can be fully tested by triggering a deployment and confirming the agent responds to a query at the cloud endpoint with a correct RAG-backed answer.

**Acceptance Scenarios**:

1. **Given** the application code is in a deployable state, **When** a developer initiates a deployment, **Then** the full system (agent, API, database, frontend) is provisioned and accessible at a cloud endpoint within 15 minutes.
2. **Given** a successful deployment, **When** a user sends a support query through the cloud-hosted API, **Then** the agent returns a RAG-backed response with citations, identical in behavior to the local development environment.
3. **Given** a successful deployment, **When** a user accesses the cloud-hosted frontend URL, **Then** the Streamlit chat interface loads and is fully functional.

---

### User Story 2 - Agent Scales Under Load (Priority: P2)

An operations team member needs the deployed agent to handle varying levels of traffic without manual intervention. When multiple users send queries simultaneously, the system automatically scales to maintain acceptable response times and scales back down when traffic subsides to control costs.

**Why this priority**: A deployment that cannot handle concurrent users has limited value beyond a demo. Auto-scaling is essential for any real evaluation or pilot use.

**Independent Test**: Can be tested by sending concurrent requests to the deployed agent and verifying responses complete within acceptable time and no requests are dropped.

**Acceptance Scenarios**:

1. **Given** the agent is deployed, **When** 10 concurrent users send queries simultaneously, **Then** all users receive responses within 30 seconds and no requests fail.
2. **Given** traffic drops to zero, **When** no requests arrive for a sustained period, **Then** compute resources scale down to minimize cost.

---

### User Story 3 - Monitor Agent Health and Performance (Priority: P2)

A developer or operations team member needs to monitor the deployed agent's health, performance, and error rates so they can identify issues before users are impacted. They access a dashboard or log stream that shows key metrics like request latency, error rates, and agent execution traces.

**Why this priority**: Without observability, diagnosing production issues becomes guesswork. This is critical for any deployment beyond a throwaway demo.

**Independent Test**: Can be tested by sending requests to the deployed agent and confirming that corresponding logs, metrics, and traces appear in the monitoring system.

**Acceptance Scenarios**:

1. **Given** the agent is deployed and processing requests, **When** a developer accesses the monitoring system, **Then** they can see request count, latency percentiles, and error rates for the last 24 hours.
2. **Given** a request fails with an error, **When** a developer reviews logs, **Then** the error is traceable to a specific agent step (routing, retrieval, tool execution, or response generation).

---

### User Story 4 - Manage Secrets and Configuration (Priority: P3)

A developer needs to securely provide API keys (LLM providers, observability tooling), database credentials, and other configuration to the deployed agent without hardcoding them in the application code or exposing them in version control.

**Why this priority**: Security is non-negotiable for any cloud deployment, but the mechanism for secret management is a well-understood problem with standard solutions. It is lower priority because it does not introduce novel risk or ambiguity.

**Independent Test**: Can be tested by deploying the agent with secrets provided through the secure configuration mechanism and confirming the agent successfully authenticates with external LLM providers and the database.

**Acceptance Scenarios**:

1. **Given** API keys and database credentials are stored in the secure configuration system, **When** the agent is deployed, **Then** it can access all required external services without any secrets appearing in code, logs, or deployment artifacts.
2. **Given** a secret needs to be rotated, **When** a developer updates the secret in the configuration system and redeploys, **Then** the agent uses the new secret without downtime.

---

### Edge Cases

- What happens when the LLM provider API (OpenAI) is temporarily unavailable during a deployed request?
- How does the system handle a database connection failure after deployment?
- What happens if a deployment is triggered while a previous deployment is still in progress?
- How does the system behave when the vector database (pgVector) runs out of storage?
- What happens when a user sends a request that exceeds the agent's configured timeout?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST deploy the complete agentic RAG support stack (LangGraph agent, FastAPI API, PostgreSQL with pgVector, Streamlit frontend) as a unified, cloud-hosted service.
- **FR-002**: System MUST expose the FastAPI API at a publicly accessible HTTPS endpoint.
- **FR-003**: System MUST expose the Streamlit frontend at a publicly accessible HTTPS endpoint.
- **FR-004**: System MUST provision a PostgreSQL database with the pgVector extension for document storage and retrieval.
- **FR-005**: System MUST automatically scale agent compute resources based on incoming request volume.
- **FR-006**: System MUST store all secrets (LLM API keys, database credentials) in a secure, centralized configuration system separate from application code.
- **FR-007**: System MUST emit structured logs for all agent requests, including agent step traces (routing, retrieval, tool execution, response generation).
- **FR-008**: System MUST provide health check endpoints that report the operational status of all system components.
- **FR-009**: System MUST support zero-downtime redeployments when application code is updated.
- **FR-010**: System MUST persist the vector database data across redeployments so that indexed documents are not lost.
- **FR-011**: System MUST enforce network isolation so that the database is not directly accessible from the public internet.
- **FR-012**: System MUST expose executor action tools as AgentCore Gateway tools backed by AWS Lambda functions; approval, audit, and guardrails MUST continue to run in-process within the agent runtime.
- **FR-013**: Each executor action tool MUST be deployed as a dedicated AWS Lambda function with its own least-privilege IAM execution role.
- **FR-014**: The in-process executor implementation MUST be removed in the same release that introduces the Gateway-routed executor; no permanent dual-path coexistence is supported.
- **FR-015**: AgentCore Gateway MUST validate inbound tool-call requests using a CUSTOM_JWT authorizer backed by a Cognito User Pool machine-to-machine app client; the AgentCore Runtime MUST obtain JWTs via OAuth2 client_credentials and present them on each Gateway call.
- **FR-016**: The agent runtime MUST emit a parent Langfuse span for each executor tool invocation and propagate the trace_id to the target Lambda; each Lambda MUST initialize the Langfuse SDK on cold start and emit a child span linked to the propagated trace_id, in addition to structured CloudWatch logs.

### Key Entities

- **Agent Runtime**: The deployed LangGraph supervisor agent that processes user queries, routes to domains, retrieves documents, and executes tools.
- **API Gateway**: The entry point for all client requests, routing to the FastAPI backend.
- **Vector Store**: The PostgreSQL + pgVector database holding indexed support documents and embeddings.
- **Frontend Application**: The Streamlit-based chat interface and observability dashboard.
- **Secret Store**: The centralized system holding API keys, credentials, and configuration values.
- **Executor Tool Lambda**: A stateless AWS Lambda function hosting exactly one executor action tool. Each Lambda has its own least-privilege IAM execution role and reads Langfuse credentials from the Secret Store on cold start.
- **AgentCore Tool Gateway**: The managed proxy that exposes executor tools to the agent. Routes agent tool-calls to the appropriate Lambda target after validating the JWT presented by the agent.
- **Identity Provider (Cognito User Pool M2M)**: The OAuth2 client_credentials JWT issuer used by the AgentCore Runtime to authenticate to the Tool Gateway.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The full system is deployable from source code to a running cloud environment in under 15 minutes.
- **SC-002**: The deployed agent returns correct, citation-backed responses to support queries with behavior identical to the local development environment.
- **SC-003**: The system handles 10 concurrent users without request failures or response times exceeding 30 seconds.
- **SC-004**: Compute costs scale proportionally with usage — idle periods incur minimal cost (under $5/day for zero traffic).
- **SC-005**: A developer can diagnose the root cause of a failed request within 5 minutes using available logs and traces.
- **SC-006**: Secrets are never exposed in deployment logs, application output, or version-controlled files.
- **SC-007**: The system can be redeployed with updated code without any user-facing downtime.

## Assumptions

- The existing application code (LangGraph agent, FastAPI API, Streamlit frontend) is functional and tested locally before deployment is attempted.
- The deploying developer has an AWS account with sufficient permissions to create the required cloud resources.
- LLM provider API keys (OpenAI) are obtained separately and provided as input to the deployment process.
- The initial deployment targets a single AWS region; multi-region redundancy is out of scope for v1.
- The vector database will be seeded with documents as a separate step after deployment; the deployment itself provisions an empty database with the correct schema and extensions.
- Cost optimization beyond auto-scaling (e.g., reserved instances, spot pricing) is out of scope for v1.
- Custom domain names and SSL certificate management are out of scope for v1; the system will use cloud-provider-generated endpoints.
- The existing Docker Compose configuration for local PostgreSQL provides the baseline for the cloud database requirements.
