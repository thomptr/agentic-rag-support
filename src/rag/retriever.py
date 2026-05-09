from src.db.connection import get_vector_store


def retrieve_documents(
    query: str,
    domain: str,
    run_id: str,
    agent: str,
    k: int = 5,
) -> list[dict]:
    """Retrieve documents filtered to a single domain (original 001 interface)."""
    vector_store = get_vector_store()

    try:
        results = vector_store.similarity_search_with_relevance_scores(
            query,
            k=k,
            filter={"domain": domain},
        )
    except Exception:
        return []

    return [
        {
            "content": doc.page_content,
            "metadata": doc.metadata,
            "score": float(score),
        }
        for doc, score in results
    ]


def retrieve_documents_multi_domain(
    query: str,
    domains: list[str],
    run_id: str,
    k: int = 5,
) -> list[dict]:
    """Retrieve documents across multiple domains using $in metadata filter."""
    vector_store = get_vector_store()

    try:
        if len(domains) == 1:
            filter_expr = {"domain": domains[0]}
        else:
            filter_expr = {"domain": {"$in": domains}}

        results = vector_store.similarity_search_with_relevance_scores(
            query,
            k=k,
            filter=filter_expr,
        )
    except Exception:
        return []

    return [
        {
            "content": doc.page_content,
            "metadata": doc.metadata,
            "score": float(score),
            "domain": doc.metadata.get("domain", "unknown"),
            "source_query": query,
        }
        for doc, score in results
    ]


def retrieve_documents_unfiltered(
    query: str,
    run_id: str,
    k: int = 15,
) -> list[dict]:
    """Retrieve documents without any domain filter (fallback for adaptive retry)."""
    vector_store = get_vector_store()

    try:
        results = vector_store.similarity_search_with_relevance_scores(query, k=k)
    except Exception:
        return []

    return [
        {
            "content": doc.page_content,
            "metadata": doc.metadata,
            "score": float(score),
            "domain": doc.metadata.get("domain", "unknown"),
            "source_query": query,
        }
        for doc, score in results
    ]
