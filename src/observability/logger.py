import structlog

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    logger_factory=structlog.PrintLoggerFactory(),
)

_log = structlog.get_logger()


def log_llm_call(
    run_id: str,
    agent: str,
    model: str,
    prompt_hash: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: float,
) -> dict:
    event = {
        "event_type": "llm_call",
        "run_id": run_id,
        "agent": agent,
        "model": model,
        "prompt_hash": prompt_hash,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
    }
    _log.info("llm_call", **event)
    return event


def log_retrieval(
    run_id: str,
    agent: str,
    query: str,
    top_k: int,
    results: list[dict],
    elapsed_ms: float,
) -> dict:
    event = {
        "event_type": "retrieval",
        "run_id": run_id,
        "agent": agent,
        "query": query,
        "top_k": top_k,
        "results": results,
        "elapsed_ms": elapsed_ms,
    }
    _log.info("retrieval", **event)
    return event


def log_routing_decision(
    run_id: str,
    query_text: str,
    classified_domain: str,
    confidence_rationale: str,
    routed_to: str,
) -> dict:
    event = {
        "event_type": "routing_decision",
        "run_id": run_id,
        "query_text": query_text,
        "classified_domain": classified_domain,
        "confidence_rationale": confidence_rationale,
        "routed_to": routed_to,
    }
    _log.info("routing_decision", **event)
    return event


def log_agent_response(
    run_id: str,
    agent: str,
    response_length: int,
    citation_count: int,
) -> dict:
    event = {
        "event_type": "agent_response",
        "run_id": run_id,
        "agent": agent,
        "response_length": response_length,
        "citation_count": citation_count,
    }
    _log.info("agent_response", **event)
    return event


# --- New 002 event helpers ---


def log_retrieval_plan(
    run_id: str,
    classified_domains: list[str],
    search_queries: list[dict],
    query_count: int,
) -> dict:
    event = {
        "event_type": "retrieval_plan",
        "run_id": run_id,
        "classified_domains": classified_domains,
        "search_queries": search_queries,
        "query_count": query_count,
    }
    _log.info("retrieval_plan", **event)
    return event


def log_multi_retrieval(
    run_id: str,
    attempt: int,
    queries_executed: int,
    total_results: int,
    unique_results: int,
    elapsed_ms: float,
    per_query_counts: list[dict] | None = None,
) -> dict:
    event = {
        "event_type": "multi_retrieval",
        "run_id": run_id,
        "attempt": attempt,
        "queries_executed": queries_executed,
        "total_results": total_results,
        "unique_results": unique_results,
        "elapsed_ms": elapsed_ms,
        "per_query_counts": per_query_counts or [],
    }
    _log.info("multi_retrieval", **event)
    return event


def log_confidence_assessment(
    run_id: str,
    attempt: int,
    score: float,
    result_count: int,
    avg_similarity: float,
    should_retry: bool,
    reason: str,
) -> dict:
    event = {
        "event_type": "confidence_assessment",
        "run_id": run_id,
        "attempt": attempt,
        "score": score,
        "result_count": result_count,
        "avg_similarity": avg_similarity,
        "should_retry": should_retry,
        "reason": reason,
    }
    _log.info("confidence_assessment", **event)
    return event


def log_retrieval_retry(
    run_id: str,
    attempt: int,
    previous_score: float,
    adjusted_params: dict,
) -> dict:
    event = {
        "event_type": "retrieval_retry",
        "run_id": run_id,
        "attempt": attempt,
        "previous_score": previous_score,
        "adjusted_params": adjusted_params,
    }
    _log.info("retrieval_retry", **event)
    return event


def log_knowledge_gap(
    run_id: str,
    final_attempt: int,
    final_score: float,
    reason: str,
) -> dict:
    event = {
        "event_type": "knowledge_gap",
        "run_id": run_id,
        "final_attempt": final_attempt,
        "final_score": final_score,
        "reason": reason,
    }
    _log.info("knowledge_gap", **event)
    return event


def log_security_check(
    run_id: str,
    signals: list[dict],
    action: str,
    latency_ms: float,
) -> dict:
    event = {
        "event_type": "security_check",
        "run_id": run_id,
        "signals": signals,
        "action": action,
        "latency_ms": latency_ms,
    }
    _log.info("security_check", **event)
    return event


def log_escalation_triggered(
    run_id: str,
    signal_name: str,
    matched_pattern: str,
    reason: str,
    agent: str,
) -> dict:
    event = {
        "event_type": "escalation_triggered",
        "run_id": run_id,
        "signal_name": signal_name,
        "matched_pattern": matched_pattern,
        "reason": reason,
        "agent": agent,
    }
    _log.info("escalation_triggered", **event)
    return event


# --- New 003 tool observability event helpers ---


def log_tool_call_attempt(
    tool_name: str,
    parameters: dict,
    risk_level: str,
    session_id: str,
) -> dict:
    event = {
        "event_type": "tool_call_attempt",
        "tool_name": tool_name,
        "parameters": parameters,
        "risk_level": risk_level,
        "session_id": session_id,
    }
    _log.info("tool_call_attempt", **event)
    return event


def log_tool_call_success(
    tool_name: str,
    parameters: dict,
    result: dict,
    duration_ms: float,
    session_id: str,
) -> dict:
    event = {
        "event_type": "tool_call_success",
        "tool_name": tool_name,
        "parameters": parameters,
        "result": result,
        "duration_ms": duration_ms,
        "session_id": session_id,
    }
    _log.info("tool_call_success", **event)
    return event


def log_tool_call_blocked(
    tool_name: str,
    parameters: dict,
    block_reason: str,
    session_id: str,
) -> dict:
    event = {
        "event_type": "tool_call_blocked",
        "tool_name": tool_name,
        "parameters": parameters,
        "block_reason": block_reason,
        "session_id": session_id,
    }
    _log.info("tool_call_blocked", **event)
    return event


def log_tool_call_failed(
    tool_name: str,
    parameters: dict,
    error: str,
    session_id: str,
) -> dict:
    event = {
        "event_type": "tool_call_failed",
        "tool_name": tool_name,
        "parameters": parameters,
        "error": error,
        "session_id": session_id,
    }
    _log.info("tool_call_failed", **event)
    return event


def log_approval_requested_event(
    approval_id: str,
    tool_name: str,
    parameters: dict,
    expires_at: str,
    session_id: str,
) -> dict:
    event = {
        "event_type": "approval_requested",
        "approval_id": approval_id,
        "tool_name": tool_name,
        "parameters": parameters,
        "expires_at": expires_at,
        "session_id": session_id,
    }
    _log.info("approval_requested", **event)
    return event


def log_approval_resolved_event(
    approval_id: str,
    status: str,
    resolved_by: str | None,
    resolution_reason: str | None,
) -> dict:
    event = {
        "event_type": "approval_resolved",
        "approval_id": approval_id,
        "status": status,
        "resolved_by": resolved_by,
        "resolution_reason": resolution_reason,
    }
    _log.info("approval_resolved", **event)
    return event
