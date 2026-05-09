from typing import Annotated, Literal

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


def _accumulate(a: list, b: list) -> list:
    return a + b


class SupportGraphState(TypedDict):
    """Shared state passed across all nodes in the support agent graph."""

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
