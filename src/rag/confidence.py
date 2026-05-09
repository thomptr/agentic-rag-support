from src.config import settings


def assess_confidence(merged_results: list[dict], attempt: int) -> dict:
    """Evaluate retrieval quality and determine whether to retry."""
    result_count = len(merged_results)

    if result_count == 0:
        return {
            "score": 0.0,
            "result_count": 0,
            "avg_similarity": 0.0,
            "should_retry": attempt < settings.max_retrieval_attempts,
            "reason": "No results retrieved",
        }

    avg_similarity = sum(d.get("score", 0.0) for d in merged_results) / result_count

    at_max_attempts = attempt >= settings.max_retrieval_attempts
    below_threshold = avg_similarity < settings.confidence_threshold
    below_min_count = result_count < settings.min_result_count

    if at_max_attempts:
        should_retry = False
        reason = (
            f"Max retrieval attempts ({settings.max_retrieval_attempts}) reached. "
            f"Final confidence: avg_similarity={avg_similarity:.3f}, result_count={result_count}"
        )
    elif below_threshold:
        should_retry = True
        reason = (
            f"Average similarity {avg_similarity:.3f} is below confidence threshold "
            f"{settings.confidence_threshold}"
        )
    elif below_min_count:
        should_retry = True
        reason = (
            f"Result count {result_count} is below minimum required {settings.min_result_count}"
        )
    else:
        should_retry = False
        reason = (
            f"Sufficient confidence: avg_similarity={avg_similarity:.3f}, "
            f"result_count={result_count}"
        )

    return {
        "score": round(avg_similarity, 4),
        "result_count": result_count,
        "avg_similarity": round(avg_similarity, 4),
        "should_retry": should_retry,
        "reason": reason,
    }
