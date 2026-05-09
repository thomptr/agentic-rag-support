# Feature Specification: LangGraph Supervisor Prototype

**Feature Branch**: `001-langgraph-supervisor-prototype`  
**Created**: 2026-05-08  
**Status**: Draft  
**Input**: User description: "Build the local LangGraph prototype with the supervisor agent and three worker agents: billing, technical and account."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Supervisor Routes a Billing Query (Priority: P1)

A customer sends a support query related to billing (e.g., "Why was I charged twice this month?"). The supervisor agent classifies the query as billing-related and routes it to the billing worker agent. The billing agent retrieves relevant knowledge-base content, reasons over it, and returns a grounded answer to the customer through the supervisor.

**Why this priority**: Routing is the core capability of the supervisor pattern. Without correct classification and delegation, no worker agent can function. This validates the entire graph flow end-to-end.

**Independent Test**: Can be fully tested by sending a billing-related query through the graph and verifying the supervisor routes to the billing agent, the billing agent retrieves context, and a grounded response is returned.

**Acceptance Scenarios**:

1. **Given** a customer query about an invoice discrepancy, **When** the query is submitted to the supervisor, **Then** the supervisor classifies it as "billing" and delegates to the billing worker agent.
2. **Given** the billing agent receives a routed query, **When** it processes the query, **Then** it retrieves relevant documents from the knowledge base and produces a response grounded in that context.
3. **Given** the billing agent produces a response, **When** the response is returned, **Then** the supervisor delivers it back to the caller with an audit trail of the routing decision.

---

### User Story 2 - Supervisor Routes a Technical Query (Priority: P2)

A customer sends a technical support query (e.g., "How do I reset my API key?"). The supervisor routes it to the technical worker agent, which retrieves relevant documentation and returns a step-by-step answer.

**Why this priority**: Validates that routing generalises beyond billing to a second domain, confirming the supervisor's classification logic is not hard-coded to a single category.

**Independent Test**: Can be fully tested by sending a technical query and verifying the supervisor routes to the technical agent, which retrieves relevant docs and returns a grounded answer.

**Acceptance Scenarios**:

1. **Given** a customer query about a technical how-to, **When** the query is submitted to the supervisor, **Then** it is classified as "technical" and routed to the technical worker agent.
2. **Given** the technical agent receives a routed query, **When** it processes the query, **Then** it retrieves relevant technical documentation and returns a step-by-step response.

---

### User Story 3 - Supervisor Routes an Account Query (Priority: P3)

A customer sends an account management query (e.g., "How do I update my email address?"). The supervisor routes it to the account worker agent, which retrieves relevant knowledge-base content and responds.

**Why this priority**: Completes the three-agent coverage. By this point the routing and worker patterns are established; this validates the third domain.

**Independent Test**: Can be fully tested by sending an account-related query and verifying routing, retrieval, and grounded response from the account agent.

**Acceptance Scenarios**:

1. **Given** a customer query about account settings, **When** the query is submitted to the supervisor, **Then** it is classified as "account" and routed to the account worker agent.
2. **Given** the account agent receives a routed query, **When** it processes the query, **Then** it retrieves relevant account documentation and returns a grounded response.

---

### User Story 4 - Supervisor Handles Ambiguous or Multi-Domain Queries (Priority: P2)

A customer sends a query that spans multiple domains (e.g., "I was charged twice and my account is locked"). The supervisor must determine the best routing strategy — either selecting the primary domain or handling a multi-step delegation.

**Why this priority**: Real customer queries are rarely cleanly categorised. This scenario validates the supervisor's robustness and prevents silent misrouting.

**Independent Test**: Can be tested by sending ambiguous queries and verifying the supervisor makes a clear routing decision with an explanation logged.

**Acceptance Scenarios**:

1. **Given** a query that touches both billing and account topics, **When** submitted to the supervisor, **Then** the supervisor selects a primary routing target and logs its reasoning for the classification decision.
2. **Given** a query that does not clearly fit any worker domain, **When** submitted to the supervisor, **Then** the supervisor returns a fallback response acknowledging it cannot confidently route the query, rather than guessing.

---

### Edge Cases

- What happens when the knowledge base contains no relevant documents for a query? The agent must acknowledge the gap rather than hallucinate.
- What happens when the supervisor cannot classify a query into any of the three domains? A fallback response must be returned.
- What happens when a worker agent's retrieval returns low-confidence results? The agent should indicate reduced confidence in its answer.
- What happens when the LLM call fails or times out? The system must return a structured error rather than crashing.
- What happens when Langfuse Cloud is unreachable? The system must fail open — continue processing the query and skip traces silently. Observability loss must never block query processing.

## Clarifications

### Session 2026-05-08

- Q: What Langfuse deployment model should be used? → A: LangFuse Cloud free tier (cloud.langfuse.com), requiring LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY environment variables.
- Q: How should Langfuse integrate with LangGraph? → A: CallbackHandler auto-instrumentation. Pass Langfuse callback to LangGraph `.invoke()` for automatic capture of all LLM/retrieval spans.
- Q: Should LangFuse replace or complement structlog? → A: Complement — keep structlog for local JSON stdout logging of all events (LLM calls, retrieval, routing decisions), add LangFuse for trace visualization and analytics.
- Q: What scope of operations should LangFuse trace? → A: Full graph execution — one trace per query with nested spans for routing, retrieval, LLM calls, and response validation.
- Q: Should the observation_logs Postgres table be kept? → A: Remove it — LangFuse handles trace persistence, structlog handles local debug output to stdout.
- Q: Should LangFuse be required or optional? → A: Optional — run without LangFuse tracing when keys are absent, log a warning at startup.
- Q: If Langfuse Cloud is unreachable during a query, should the system continue or error? → A: Fail open — continue processing, skip traces silently. Langfuse unavailability must never block query processing.
- Q: Should LangFuse traces include custom metadata for dashboard filtering? → A: Yes — tag each trace with query_id, classified_domain, agent_name, and session_id as LangFuse trace metadata for filtering and search.
- Q: Should pending LangFuse traces be flushed on server shutdown? → A: Yes — flush pending traces in the FastAPI lifespan shutdown hook to prevent data loss on graceful shutdown.
- Q: When LangFuse keys are present but invalid, what should happen at startup? → A: Fail fast at startup with a clear error message explaining the invalid credentials. Absent keys = skip tracing; present but invalid keys = startup error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST implement a supervisor agent that receives customer support queries and classifies them into one of three domains: billing, technical, or account.
- **FR-002**: System MUST implement three worker agents (billing, technical, account), each capable of handling queries within its domain.
- **FR-003**: The supervisor MUST route each query to exactly one worker agent based on its classification.
- **FR-004**: Each worker agent MUST query the retrieval layer (knowledge base) before generating any response (RAG-first principle).
- **FR-005**: Each worker agent MUST return a response that is grounded in retrieved context — responses without retrieved evidence are a critical failure.
- **FR-006**: The supervisor MUST return the worker agent's response to the caller along with metadata indicating which agent handled the query and the routing rationale.
- **FR-007**: System MUST provide a fallback response when the supervisor cannot confidently classify a query into any domain.
- **FR-008**: Every LLM call MUST be logged via structlog to stdout (model, prompt hash, input tokens, output tokens, latency) AND captured as a LangFuse trace span when LangFuse is configured.
- **FR-009**: Every retrieval call MUST be logged via structlog to stdout (query, top-k results with scores, elapsed time) AND captured as a LangFuse trace span when LangFuse is configured.
- **FR-010**: All agent decisions (retrieve, route, respond, fallback) MUST emit structured log events via structlog for local replay AND produce LangFuse trace spans when LangFuse is configured.
- **FR-011**: The graph workflow MUST be implemented using LangGraph with a clearly defined state schema shared across all agents.
- **FR-012**: System MUST be runnable locally from the command line without requiring external infrastructure beyond a vector store and LLM API keys. LangFuse Cloud is optional for enhanced observability.
- **FR-013**: The system MUST integrate LangFuse (Cloud) for distributed tracing using the LangChain `CallbackHandler` for automatic instrumentation of all LangGraph node executions, LLM calls, and retrieval operations. Each LangFuse trace MUST be tagged with custom metadata: `query_id`, `classified_domain`, `agent_name`, and `session_id` for dashboard filtering and search. LangFuse MUST be optional — the system runs without it when LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are absent, logging a warning at startup. When keys are present but invalid (auth failure), the system MUST fail fast at startup with a clear error message. When LangFuse is configured and valid, the FastAPI lifespan shutdown hook MUST flush pending traces to prevent data loss on graceful shutdown. `structlog` provides local JSON logging of all events (LLM calls, retrieval, routing, errors) regardless of LangFuse availability.
- **FR-014**: The `observation_logs` Postgres table is NOT used. Trace persistence is handled by LangFuse Cloud; local debug output is handled by structlog to stdout.

### Key Entities

- **Customer Query**: The inbound support request; contains the user's question text and optional session context.
- **Supervisor Agent**: The entry-point agent that classifies queries and routes them to the appropriate worker.
- **Worker Agent**: A domain-specific agent (billing, technical, or account) that retrieves context and generates a grounded response.
- **Knowledge Base**: The collection of domain-specific documents used for retrieval-augmented generation.
- **Routing Decision**: The supervisor's classification output, including the chosen domain and confidence rationale.
- **Agent Response**: The final output containing the answer text, source references, the handling agent, and observability metadata.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The supervisor correctly routes queries to the appropriate domain agent at least 90% of the time across a representative test set.
- **SC-002**: Every agent response includes at least one citation from the knowledge base — zero-citation responses constitute a test failure.
- **SC-003**: End-to-end query processing (from submission to response) completes in under 30 seconds for a single query on a local machine.
- **SC-004**: The system handles all three domains (billing, technical, account) with at least 3 sample queries each producing grounded responses.
- **SC-005**: Every run produces a complete structured log trail (via structlog to stdout) that can be used to trace the full routing and retrieval chain. When LangFuse is configured, a complete trace with nested spans for routing, retrieval, and LLM calls is also visible in the LangFuse dashboard.
- **SC-006**: The prototype runs locally with a single command after environment setup, requiring no cloud infrastructure beyond LLM API keys. LangFuse Cloud is optional for enhanced trace visualization.

## Assumptions

- This is a proof-of-concept; production hardening, scaling, and deployment are out of scope.
- LangGraph is used as the graph orchestration framework; Claude (via the Anthropic SDK) is the LLM provider, consistent with the project constitution.
- PostgreSQL 16 with pgvector is used for the knowledge base vector store and relational data (resolved during implementation planning; formerly "ChromaDB or FAISS").
- The knowledge base will be seeded with sample documents for each domain (billing, technical, account) sufficient to demonstrate retrieval; real production data is not required.
- Only three worker agents are in scope for this feature (billing, technical, account). The product and retention agents shown in the project layout are deferred to future features.
- The system is invoked via FastAPI endpoints; a web frontend is not in scope for this feature (updated from CLI-only per user decision during planning).
- Users have Python 3.11+ and access to an Anthropic API key and an OpenAI API key (for embeddings). LangFuse Cloud API keys (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY) are optional for trace visualization.
- `structlog` provides local JSON logging of all events (LLM calls, retrieval, routing decisions, errors, startup) to stdout. LangFuse Cloud complements structlog with distributed trace visualization when configured.
- LangFuse tracing is captured automatically by the LangChain `CallbackHandler` — no custom trace instrumentation code is required. The handler is attached only when LangFuse keys are present.
- The `observation_logs` Postgres table is removed — LangFuse handles trace persistence; structlog handles local debug output.
