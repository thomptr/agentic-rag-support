"""Technical domain agent — profile-driven response generation.

Mirror of `billing_agent`: reads `state["merged_results"]` populated by the
shared multi_retriever pipeline; runs the LLM with the technical-domain
system prompt from the profile.
"""

from __future__ import annotations

import hashlib
import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.agents.profiles import AGENT_PROFILES
from src.config import settings
from src.graph.state import SupportGraphState
from src.observability.logger import log_agent_response, log_llm_call
from src.tools.registry import get_tools_for_agent, llm_tool_calls_to_planned

_PROFILE = AGENT_PROFILES["technical_agent"]


def technical_agent(state: SupportGraphState) -> dict:
    query_text = state["query_text"]
    run_id = state["run_id"]
    docs = state.get("merged_results") or []

    if docs:
        context = "\n\n---\n\n".join(
            f"[Source: {d.get('title') or d.get('metadata', {}).get('title', 'Unknown')} | "
            f"{d.get('source_file') or d.get('metadata', {}).get('source_file', '')}]\n"
            f"{d.get('content') or d.get('chunk_text', '')}"
            for d in docs
        )
    else:
        context = "No relevant documents found in the technical knowledge base."

    llm = ChatOpenAI(model=settings.llm_model, api_key=settings.openai_api_key)
    tools = get_tools_for_agent(_PROFILE.name)
    if tools:
        llm = llm.bind_tools(tools)
    messages = [
        SystemMessage(content=_PROFILE.system_prompt),
        HumanMessage(
            content=(
                f"Customer technical query: {query_text}\n\n"
                f"Retrieved technical knowledge base documents:\n\n{context}"
            )
        ),
    ]

    start = time.perf_counter()
    planned_tool_calls: list[dict] = []
    try:
        response = llm.invoke(messages)
        response_text = response.content or ""
        planned_tool_calls = llm_tool_calls_to_planned(getattr(response, "tool_calls", None))
    except Exception:
        response_text = (
            "I apologize — I encountered an error while processing your technical inquiry. "
            "Please contact our technical support team directly for immediate assistance."
        )
    latency_ms = (time.perf_counter() - start) * 1000

    llm_event = log_llm_call(
        run_id=run_id,
        agent=_PROFILE.name,
        model=settings.llm_model,
        prompt_hash=hashlib.md5(query_text.encode()).hexdigest()[:8],
        input_tokens=0,
        output_tokens=0,
        latency_ms=latency_ms,
    )

    citations = [
        {
            "doc_id": d.get("doc_id") or d.get("metadata", {}).get("doc_id", ""),
            "chunk_text": (d.get("content") or d.get("chunk_text", ""))[:300],
            "score": d.get("score", 0.0),
            "title": d.get("title") or d.get("metadata", {}).get("title", ""),
            "source_file": d.get("source_file") or d.get("metadata", {}).get("source_file", ""),
        }
        for d in docs
    ]

    response_event = log_agent_response(
        run_id=run_id,
        agent=_PROFILE.name,
        response_length=len(response_text),
        citation_count=len(citations),
    )

    return {
        "response_text": response_text,
        "citations": citations,
        "current_node": _PROFILE.name,
        "tool_calls": planned_tool_calls,
        "action_needed": bool(planned_tool_calls) or _detect_action_needed(query_text),
        "log_events": [llm_event, response_event],
    }


_ACTION_KEYWORDS = (
    "open a ticket",
    "create a ticket",
    "submit a ticket",
    "create a support ticket",
    "open a support ticket",
    "escalate",
    "file a bug",
)


def _detect_action_needed(query_text: str) -> bool:
    lowered = query_text.lower()
    return any(kw in lowered for kw in _ACTION_KEYWORDS)
