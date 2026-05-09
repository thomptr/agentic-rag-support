from typing import Annotated, Literal

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


def _accumulate(a: list, b: list) -> list:
    return a + b


class SupportGraphState(TypedDict):
    """Shared state passed across all nodes in the support agent graph."""

    # --- Existing fields (from 001) ---
    query_id: str
    query_text: str

    messages: Annotated[list[BaseMessage], add_messages]

    classified_domain: Literal["billing", "technical", "account", "unknown"] | None
    confidence_rationale: str | None
    routed_to_agent: str | None

    retrieved_documents: list[dict] | None

    response_text: str | None
    citations: list[dict] | None

    run_id: str
    log_events: Annotated[list[dict], _accumulate]

    # --- New fields (002: multi-document retrieval) ---

    # Supervisor now classifies to one or more domains
    classified_domains: list[str] | None

    # Multi-query: generated search query variations
    # Each entry: { "query": str, "target_domain": str, "aspect": str }
    search_queries: list[dict] | None

    # Retrieval results before merge (raw results from all queries)
    raw_retrieval_results: Annotated[list[dict], _accumulate] | None

    # Merged, deduplicated, ranked results
    # Each entry: { "content": str, "metadata": dict, "score": float, "domain": str, "source_query": str }
    merged_results: list[dict] | None

    # Confidence assessment
    # { "score": float, "result_count": int, "avg_similarity": float, "should_retry": bool, "reason": str }
    retrieval_confidence: dict | None

    # Retry tracking
    retrieval_attempt: int
    max_retrieval_attempts: int

    # Policy gate (security_check) — present when the policy gate has run
    # Each signal entry: { "name": str, "matched_pattern": str, "severity": str, "action": str }
    security_signals: list[dict] | None
    escalation_required: bool | None
    escalation_reason: str | None
