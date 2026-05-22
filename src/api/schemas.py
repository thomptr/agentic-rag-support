from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query_text: str = Field(..., min_length=1, max_length=10000)
    session_id: str | None = None
    guardrails_enabled: bool | None = None
    model_override: str | None = None


class CitationResponse(BaseModel):
    content: str = ""
    domain: str = ""
    source: str = ""
    score: float = 0.0
    # Legacy fields preserved for backwards compatibility
    doc_id: str = ""
    chunk_text: str = ""
    title: str = ""
    source_file: str = ""


class QueryMetadata(BaseModel):
    classified_domain: str | None = None
    classified_domains: list[str] = []
    run_id: str
    total_latency_ms: float
    llm_calls: int
    retrieval_calls: int
    retrieval_attempts: int = 0
    documents_retrieved: int = 0
    documents_after_dedup: int = 0
    retrieval_confidence: float | None = None


class ToolCallResult(BaseModel):
    tool_name: str
    status: str
    result: dict | None = None
    error: str | None = None
    block_reason: str | None = None
    approval_id: str | None = None


class ApprovalItem(BaseModel):
    id: str
    tool_name: str
    parameters: dict
    status: str
    created_at: str
    expires_at: str


class QueryResponse(BaseModel):
    query_id: str
    response_text: str
    agent: str
    routing_rationale: str | None
    citations: list[CitationResponse]
    metadata: QueryMetadata
    # Tool execution metadata (003)
    tool_calls: list[ToolCallResult] = []
    action_taken: bool = False
    pending_approvals: list[ApprovalItem] = []
    # T124: trace identifier the agent generates per invocation. When the agent
    # publishes Langfuse spans, this id is used as the trace_id so a developer
    # can look the request up directly. When Langfuse isn't configured, it's
    # still useful as a request-correlation key for CloudWatch log searches.
    langfuse_trace_id: str | None = None


class LangfuseStatus(BaseModel):
    # "ok" — client initialized and traces will land in the Langfuse UI.
    # "disabled" — credentials absent; local-mode traffic is invisible.
    # "failed" — credentials present but init raised (e.g. bad rotation).
    state: str
    source: str = ""  # "secrets_manager" | "env" | ""
    host: str = ""
    reason: str = ""


class HealthResponse(BaseModel):
    status: str
    database: str
    vector_store: str
    llm: str
    langfuse: LangfuseStatus


# Approval API schemas


class ApprovalListResponse(BaseModel):
    approvals: list[ApprovalItem]


class ApproveRequest(BaseModel):
    reviewer: str
    reason: str


class RejectRequest(BaseModel):
    reviewer: str
    reason: str


class ApprovalResponse(BaseModel):
    id: str
    status: str
    tool_name: str
    result: dict | None = None
    error: str | None = None


class RejectResponse(BaseModel):
    id: str
    status: str
    reason: str
