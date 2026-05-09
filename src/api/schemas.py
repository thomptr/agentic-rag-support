from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query_text: str = Field(..., min_length=1, max_length=10000)
    session_id: str | None = None


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


class QueryResponse(BaseModel):
    query_id: str
    response_text: str
    agent: str
    routing_rationale: str | None
    citations: list[CitationResponse]
    metadata: QueryMetadata


class HealthResponse(BaseModel):
    status: str
    database: str
    vector_store: str
    llm: str
