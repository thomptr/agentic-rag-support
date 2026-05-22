from src.config import settings


def assess_confidence(merged_results: list[dict], attempt: int) -> dict:
    """Evaluate retrieval quality and determine whether to retry.

    Gating uses the **mean of the top-K result scores** (K from
    ``settings.confidence_top_k``, default 3) rather than the average over
    every result. Long-tail noise — common when broadened-fallback retrieval
    pulls in marginal matches — used to drag ``avg_similarity`` below the
    threshold even when the best evidence was strong. Top-K mean reflects
    "is the best evidence good enough?" which is what the downstream agent
    actually consumes.

    ``avg_similarity`` is preserved in the returned dict for diagnostic
    visibility (and for backward compatibility with the Langfuse logger and
    existing log consumers); it no longer influences the retry decision.
    """
    result_count = len(merged_results)

    if result_count == 0:
        return {
            "score": 0.0,
            "result_count": 0,
            "avg_similarity": 0.0,
            "top_k": 0,
            "should_retry": attempt < settings.max_retrieval_attempts,
            "reason": "No results retrieved",
        }

    scores = [d.get("score", 0.0) for d in merged_results]
    avg_similarity = sum(scores) / result_count

    k = min(settings.confidence_top_k, result_count)
    top_k_score = sum(sorted(scores, reverse=True)[:k]) / k

    at_max_attempts = attempt >= settings.max_retrieval_attempts
    below_threshold = top_k_score < settings.confidence_threshold
    below_min_count = result_count < settings.min_result_count

    if at_max_attempts:
        should_retry = False
        reason = (
            f"Max retrieval attempts ({settings.max_retrieval_attempts}) reached. "
            f"Final confidence: top{k}_mean={top_k_score:.3f}, "
            f"avg_similarity={avg_similarity:.3f}, result_count={result_count}"
        )
    elif below_threshold:
        should_retry = True
        reason = (
            f"Top-{k} mean {top_k_score:.3f} is below confidence threshold "
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
            f"Sufficient confidence: top{k}_mean={top_k_score:.3f}, result_count={result_count}"
        )

    return {
        "score": round(top_k_score, 4),
        "result_count": result_count,
        "avg_similarity": round(avg_similarity, 4),
        "top_k": k,
        "should_retry": should_retry,
        "reason": reason,
    }
