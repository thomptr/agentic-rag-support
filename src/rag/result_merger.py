import hashlib

from src.config import settings


def merge_results(raw_results: list[dict]) -> list[dict]:
    """Deduplicate by content hash, rank by similarity score, cap at MAX_CONTEXT_DOCUMENTS."""
    if not raw_results:
        return []

    # Deduplicate: keep the highest-score copy of each unique content chunk
    seen: dict[str, dict] = {}
    for doc in raw_results:
        content = doc.get("content", "")
        content_hash = hashlib.md5(content.encode()).hexdigest()
        if content_hash not in seen or doc.get("score", 0.0) > seen[content_hash].get("score", 0.0):
            seen[content_hash] = doc

    # Rank by descending similarity score
    deduplicated = sorted(seen.values(), key=lambda d: d.get("score", 0.0), reverse=True)

    # Cap at MAX_CONTEXT_DOCUMENTS
    return deduplicated[: settings.max_context_documents]
