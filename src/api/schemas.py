from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query_text: str = Field(..., min_length=1, max_length=10000)
    session_id: str | None = None


class CitationResponse(BaseModel):
    doc_id: str
    chunk_text: str
    score: float
    title: str = ""
    source_file: str = ""


class QueryMetadata(BaseModel):
    classified_domain: str | None
    run_id: str
    total_latency_ms: float
    llm_calls: int
    retrieval_calls: int


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
