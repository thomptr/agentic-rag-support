import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from src.api.schemas import (
    ApprovalItem,
    ApprovalListResponse,
    ApprovalResponse,
    ApproveRequest,
    CitationResponse,
    HealthResponse,
    QueryMetadata,
    QueryRequest,
    QueryResponse,
    RejectRequest,
    RejectResponse,
    ToolCallResult,
)
from src.config import settings
from src.graph.workflow import graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Agentic RAG Support",
    description="LangGraph supervisor agent for customer support",
    version="0.2.0",
    lifespan=lifespan,
)


_ALLOWED_MODELS = {"gpt-4o-mini", "gpt-4o", "claude-sonnet-4-6"}


@app.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest) -> QueryResponse:
    if not request.query_text.strip():
        raise HTTPException(status_code=422, detail="query_text must not be empty")

    if request.model_override is not None and request.model_override not in _ALLOWED_MODELS:
        raise HTTPException(
            status_code=422,
            detail=f"model_override must be one of: {sorted(_ALLOWED_MODELS)}",
        )

    query_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    session_id = request.session_id or query_id

    initial_state = {
        "query_id": query_id,
        "query_text": request.query_text,
        "messages": [],
        "classified_domain": None,
        "classified_domains": None,
        "confidence_rationale": None,
        "routed_to_agent": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": run_id,
        "log_events": [],
        "search_queries": None,
        "raw_retrieval_results": None,
        "merged_results": None,
        "retrieval_confidence": None,
        "retrieval_attempt": 0,
        "max_retrieval_attempts": settings.max_retrieval_attempts,
        # Tool execution state (003)
        "session_id": session_id,
        "tool_calls": None,
        "tool_results": None,
        "pending_approvals": None,
        "action_taken": None,
        "action_needed": None,
        # Per-request overrides (004: frontend)
        "guardrails_enabled": request.guardrails_enabled,
        "model_override": request.model_override,
    }

    start = time.perf_counter()
    result = graph.invoke(initial_state)
    total_latency_ms = (time.perf_counter() - start) * 1000

    log_events = result.get("log_events", [])
    llm_calls = sum(1 for e in log_events if e.get("event_type") == "llm_call")
    retrieval_calls = sum(1 for e in log_events if e.get("event_type") == "multi_retrieval")

    raw_citations = result.get("citations") or []
    citations = [
        CitationResponse(
            content=c.get("content", c.get("chunk_text", "")),
            domain=c.get("domain", ""),
            source=c.get("source", c.get("source_file", "")),
            score=float(c.get("score", 0.0)),
            doc_id=c.get("doc_id", ""),
            chunk_text=c.get("chunk_text", c.get("content", "")),
            title=c.get("title", ""),
            source_file=c.get("source_file", c.get("source", "")),
        )
        for c in raw_citations
    ]

    retrieval_confidence_val = result.get("retrieval_confidence") or {}
    raw_retrieval_results = result.get("raw_retrieval_results") or []
    merged_results = result.get("merged_results") or []

    raw_tool_results = result.get("tool_results") or []
    tool_calls_resp = [
        ToolCallResult(
            tool_name=tr.get("tool_name", ""),
            status=tr.get("status", ""),
            result=tr.get("result"),
            error=tr.get("error"),
            block_reason=tr.get("block_reason"),
            approval_id=tr.get("approval_id"),
        )
        for tr in raw_tool_results
    ]

    raw_pending = result.get("pending_approvals") or []
    pending_approvals_resp = [
        ApprovalItem(
            id=p.get("id", ""),
            tool_name=p.get("tool_name", ""),
            parameters=p.get("parameters", {}),
            status=p.get("status", "pending"),
            created_at=p.get("created_at", ""),
            expires_at=p.get("expires_at", ""),
        )
        for p in raw_pending
    ]

    return QueryResponse(
        query_id=query_id,
        response_text=result.get("response_text") or "",
        agent=result.get("routed_to_agent") or "unknown",
        routing_rationale=result.get("confidence_rationale"),
        citations=citations,
        metadata=QueryMetadata(
            classified_domain=result.get("classified_domain"),
            classified_domains=result.get("classified_domains") or [],
            run_id=run_id,
            total_latency_ms=round(total_latency_ms, 2),
            llm_calls=llm_calls,
            retrieval_calls=retrieval_calls,
            retrieval_attempts=result.get("retrieval_attempt", 0),
            documents_retrieved=len(raw_retrieval_results),
            documents_after_dedup=len(merged_results),
            retrieval_confidence=retrieval_confidence_val.get("score"),
        ),
        tool_calls=tool_calls_resp,
        action_taken=bool(result.get("action_taken")),
        pending_approvals=pending_approvals_resp,
    )


@app.get("/approvals", response_model=ApprovalListResponse)
async def list_approvals() -> ApprovalListResponse:
    from src.tools.approval import list_pending

    pending = list_pending()
    items = [
        ApprovalItem(
            id=a.id,
            tool_name=a.tool_name,
            parameters=a.parameters,
            status=a.status,
            created_at=a.created_at.isoformat(),
            expires_at=a.expires_at.isoformat(),
        )
        for a in pending
    ]
    return ApprovalListResponse(approvals=items)


@app.post("/approvals/{approval_id}/approve", response_model=ApprovalResponse)
async def approve_action(approval_id: str, request: ApproveRequest) -> ApprovalResponse:
    from src.tools.approval import approve

    try:
        result = approve(approval_id, reviewer=request.reviewer, reason=request.reason)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Approval '{approval_id}' not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return ApprovalResponse(
        id=result["id"],
        status=result["status"],
        tool_name=result["tool_name"],
        result=result.get("result"),
        error=result.get("error"),
    )


@app.post("/approvals/{approval_id}/reject", response_model=RejectResponse)
async def reject_action(approval_id: str, request: RejectRequest) -> RejectResponse:
    from src.tools.approval import reject

    try:
        result = reject(approval_id, reviewer=request.reviewer, reason=request.reason)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Approval '{approval_id}' not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return RejectResponse(
        id=result["id"],
        status=result["status"],
        reason=result["reason"],
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
