from src.graph.state import SupportGraphState

_LOW_CONFIDENCE_THRESHOLD = 0.5


def validate_response(state: SupportGraphState) -> dict:
    citations = state.get("citations") or []
    response_text = state.get("response_text") or ""
    merged_results = state.get("merged_results") or []
    retrieved_docs = merged_results or (state.get("retrieved_documents") or [])
    retrieval_confidence = state.get("retrieval_confidence") or {}
    run_id = state.get("run_id", "")

    citations_valid = len(citations) > 0
    response_valid = len(response_text.strip()) > 0

    scores = [d.get("score", 1.0) for d in retrieved_docs if isinstance(d, dict)]
    avg_score = sum(scores) / len(scores) if scores else 1.0
    low_confidence = avg_score < _LOW_CONFIDENCE_THRESHOLD

    # Count citations per domain for multi-domain validation
    domains_cited = {c.get("domain", "unknown") for c in citations if isinstance(c, dict)}

    retrieval_attempts = state.get("retrieval_attempt", 0)
    documents_retrieved = len(state.get("raw_retrieval_results") or [])
    documents_after_dedup = len(merged_results)
    final_confidence_score = retrieval_confidence.get("score", avg_score)

    validation_event = {
        "event_type": "validation",
        "run_id": run_id,
        "citations_valid": citations_valid,
        "response_valid": response_valid,
        "citation_count": len(citations),
        "response_length": len(response_text),
        "avg_score": round(avg_score, 4),
        "low_confidence": low_confidence,
        "domains_cited": list(domains_cited),
        "retrieval_attempts": retrieval_attempts,
        "documents_retrieved": documents_retrieved,
        "documents_after_dedup": documents_after_dedup,
        "final_confidence_score": round(final_confidence_score, 4),
    }

    return {
        "log_events": [validation_event],
    }
