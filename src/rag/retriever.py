from src.db.connection import get_vector_store


def retrieve_documents(
    query: str,
    domain: str,
    run_id: str,
    agent: str,
    k: int = 5,
) -> list[dict]:
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
