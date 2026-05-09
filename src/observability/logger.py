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
