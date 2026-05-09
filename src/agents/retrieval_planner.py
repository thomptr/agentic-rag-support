from src.config import settings
from src.graph.state import SupportGraphState
from src.observability.logger import log_retrieval_plan
from src.rag.query_generator import generate_search_queries

_ALL_DOMAINS = ["billing", "technical", "account"]


def retrieval_planner(state: SupportGraphState) -> dict:
    """Generate search query variations targeting classified domains.

    Progressive retry broadening per research.md:
    - Attempt 1: domain-filtered, k=5 (standard)
    - Attempt 2: broaden to all 3 domains, k=10
    - Attempt 3: no domain filter, k=15
    """
    query_text = state["query_text"]
    classified_domains = state.get("classified_domains") or ["unknown"]
    run_id = state["run_id"]
    current_attempt = state.get("retrieval_attempt", 0)
    new_attempt = current_attempt + 1

    if new_attempt >= 3:
        # Final attempt: no domain filter — search all domains with highest k
        search_queries = [
            {
                "query": query_text,
                "target_domain": "all",
                "aspect": "broad fallback — no domain filter",
            }
        ]
    elif new_attempt == 2:
        # Retry: broaden to all 3 domains
        search_queries = generate_search_queries(
            query_text=query_text,
            classified_domains=_ALL_DOMAINS,
        )
    else:
        # First attempt: use only classified domains
        search_queries = generate_search_queries(
            query_text=query_text,
            classified_domains=classified_domains,
        )

    plan_event = log_retrieval_plan(
        run_id=run_id,
        classified_domains=classified_domains,
        search_queries=search_queries,
        query_count=len(search_queries),
    )

    return {
        "search_queries": search_queries,
        "retrieval_attempt": new_attempt,
        "max_retrieval_attempts": settings.max_retrieval_attempts,
        "log_events": [plan_event],
    }
