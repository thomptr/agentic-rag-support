from src.graph.state import SupportGraphState

_LOW_CONFIDENCE_THRESHOLD = 0.5


def validate_response(state: SupportGraphState) -> dict:
    citations = state.get("citations") or []
    response_text = state.get("response_text") or ""
    retrieved_docs = state.get("retrieved_documents") or []
    run_id = state.get("run_id", "")

    citations_valid = len(citations) > 0
    response_valid = len(response_text.strip()) > 0

    scores = [d.get("score", 1.0) for d in retrieved_docs if isinstance(d, dict)]
    avg_score = sum(scores) / len(scores) if scores else 1.0
    low_confidence = avg_score < _LOW_CONFIDENCE_THRESHOLD

    validation_event = {
        "event_type": "validation",
        "run_id": run_id,
        "citations_valid": citations_valid,
        "response_valid": response_valid,
        "citation_count": len(citations),
        "response_length": len(response_text),
        "avg_score": round(avg_score, 4),
        "low_confidence": low_confidence,
    }

    return {
        "log_events": [validation_event],
    }
