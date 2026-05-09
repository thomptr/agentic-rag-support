import time

from src.graph.state import SupportGraphState
from src.observability.logger import log_multi_retrieval
from src.rag.result_merger import merge_results
from src.rag.retriever import retrieve_documents_multi_domain, retrieve_documents_unfiltered


def multi_retriever(state: SupportGraphState) -> dict:
    """Execute search queries across domains, deduplicate, and rank results."""
    search_queries = state.get("search_queries") or []
    classified_domains = state.get("classified_domains") or []
    retrieval_attempt = state.get("retrieval_attempt", 1)
    run_id = state["run_id"]

    # Determine k based on attempt number
    if retrieval_attempt >= 3:
        k = 15
    elif retrieval_attempt == 2:
        k = 10
    else:
        k = 5

    start = time.perf_counter()
    raw_results: list[dict] = []
    per_query_counts: list[dict] = []

    for sq in search_queries:
        query = sq.get("query", "")
        target_domain = sq.get("target_domain", "all")

        if target_domain == "all" or not classified_domains:
            docs = retrieve_documents_unfiltered(query=query, run_id=run_id, k=k)
        else:
            # Use domain from query if it differs from classified_domains (multi-query case)
            domains_to_search = (
                [target_domain] if target_domain in classified_domains else classified_domains
            )
            docs = retrieve_documents_multi_domain(
                query=query,
                domains=domains_to_search,
                run_id=run_id,
                k=k,
            )

        # Ensure domain and source_query are set on each result
        for doc in docs:
            doc.setdefault("domain", doc.get("metadata", {}).get("domain", "unknown"))
            doc.setdefault("source_query", query)

        raw_results.extend(docs)
        per_query_counts.append(
            {
                "query": sq.get("query", ""),
                "target_domain": target_domain,
                "result_count": len(docs),
            }
        )

    total_results = len(raw_results)
    merged = merge_results(raw_results)
    elapsed_ms = (time.perf_counter() - start) * 1000

    retrieval_event = log_multi_retrieval(
        run_id=run_id,
        attempt=retrieval_attempt,
        queries_executed=len(search_queries),
        total_results=total_results,
        unique_results=len(merged),
        elapsed_ms=round(elapsed_ms, 2),
        per_query_counts=per_query_counts,
    )

    return {
        "raw_retrieval_results": raw_results,
        "merged_results": merged,
        "retrieved_documents": merged,
        "log_events": [retrieval_event],
    }
