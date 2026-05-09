import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from src.api.schemas import (
    CitationResponse,
    HealthResponse,
    QueryMetadata,
    QueryRequest,
    QueryResponse,
)
from src.config import settings
from src.graph.workflow import graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify DB connection and vector store on first request
    # For now, we initialize lazily to avoid blocking startup
    yield


app = FastAPI(
    title="Agentic RAG Support",
    description="LangGraph supervisor agent for customer support",
    version="0.1.0",
    lifespan=lifespan,
)


@app.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest) -> QueryResponse:
    if not request.query_text.strip():
        raise HTTPException(status_code=422, detail="query_text must not be empty")

    query_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    initial_state = {
        "query_id": query_id,
        "query_text": request.query_text,
        "messages": [],
        "classified_domain": None,
        "confidence_rationale": None,
        "routed_to_agent": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": run_id,
        "log_events": [],
    }

    start = time.perf_counter()
    result = graph.invoke(initial_state)
    total_latency_ms = (time.perf_counter() - start) * 1000

    log_events = result.get("log_events", [])
    llm_calls = sum(1 for e in log_events if e.get("event_type") == "llm_call")
    retrieval_calls = sum(1 for e in log_events if e.get("event_type") == "retrieval")

    raw_citations = result.get("citations") or []
    citations = [
        CitationResponse(
            doc_id=c.get("doc_id", ""),
            chunk_text=c.get("chunk_text", ""),
            score=float(c.get("score", 0.0)),
            title=c.get("title", ""),
            source_file=c.get("source_file", ""),
        )
        for c in raw_citations
    ]

    return QueryResponse(
        query_id=query_id,
        response_text=result.get("response_text") or "",
        agent=result.get("routed_to_agent") or "unknown",
        routing_rationale=result.get("confidence_rationale"),
        citations=citations,
        metadata=QueryMetadata(
            classified_domain=result.get("classified_domain"),
            run_id=run_id,
            total_latency_ms=round(total_latency_ms, 2),
            llm_calls=llm_calls,
            retrieval_calls=retrieval_calls,
        ),
    )


@app.get("/health", response_model=HealthResponse)
async def health_endpoint() -> HealthResponse:
    db_status = "disconnected"
    vs_status = "not_ready"
    llm_status = "not_configured"

    try:
        import psycopg

        conn_str = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
        with psycopg.connect(conn_str, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        db_status = "connected"
        vs_status = "ready"
    except Exception:
        pass

    if settings.openai_api_key and settings.openai_api_key.startswith("sk-"):
        llm_status = "configured"

    return HealthResponse(
        status="healthy",
        database=db_status,
        vector_store=vs_status,
        llm=llm_status,
    )
