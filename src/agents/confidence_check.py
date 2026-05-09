from langgraph.types import Command

from src.graph.state import SupportGraphState
from src.observability.logger import log_confidence_assessment, log_retrieval_retry
from src.rag.confidence import assess_confidence


def confidence_check(state: SupportGraphState) -> Command:
    """Evaluate retrieval quality and decide whether to retry or proceed."""
    merged_results = state.get("merged_results") or []
    retrieval_attempt = state.get("retrieval_attempt", 1)
    run_id = state["run_id"]

    assessment = assess_confidence(merged_results, attempt=retrieval_attempt)

    confidence_event = log_confidence_assessment(
        run_id=run_id,
        attempt=retrieval_attempt,
        score=assessment["score"],
        result_count=assessment["result_count"],
        avg_similarity=assessment["avg_similarity"],
        should_retry=assessment["should_retry"],
        reason=assessment["reason"],
    )

    log_events = [confidence_event]

    if assessment["should_retry"]:
        retry_event = log_retrieval_retry(
            run_id=run_id,
            attempt=retrieval_attempt + 1,
            previous_score=assessment["score"],
            adjusted_params={
                "k": 10 if retrieval_attempt < 2 else 15,
                "domain_filter": "broadened" if retrieval_attempt < 2 else "none",
            },
        )
        log_events.append(retry_event)
        return Command(
            goto="retrieval_planner",
            update={
                "retrieval_confidence": assessment,
                "log_events": log_events,
            },
        )

    return Command(
        goto="response_generator",
        update={
            "retrieval_confidence": assessment,
            "log_events": log_events,
        },
    )
