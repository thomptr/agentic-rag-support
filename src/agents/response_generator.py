import hashlib
import time

from langchain_core.messages import HumanMessage as HMsg
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from src.config import settings
from src.graph.state import SupportGraphState
from src.observability.logger import log_agent_response, log_knowledge_gap, log_llm_call

_SYSTEM_PROMPT = """You are a customer support specialist. Your answers must be grounded in the retrieved documents provided.

Rules:
- ALWAYS base your response on the retrieved documents
- Cite the specific document(s) that support each part of your answer
- If documents span multiple domains (billing, technical, account), address each domain clearly
- If retrieved documents do not fully answer the question, acknowledge what is not covered
- Be concise and helpful"""

_RESPONSE_PROMPT = """Customer question: {question}

Retrieved knowledge base documents:
{context}

Provide a helpful, grounded response based on the documents above. Cite the source documents."""

_GAP_PROMPT = """Customer question: {question}

Our knowledge base was searched but did not return sufficient results to confidently answer this question.

Generate a helpful knowledge gap acknowledgment that:
1. Acknowledges we don't have enough information to fully answer
2. Suggests contacting a human support agent
3. Does NOT fabricate any information"""


def response_generator(state: SupportGraphState) -> dict:
    """Generate a grounded response with citations from merged retrieval results."""
    query_text = state["query_text"]
    merged_results = state.get("merged_results") or []
    retrieval_confidence = state.get("retrieval_confidence") or {}
    run_id = state["run_id"]

    is_knowledge_gap = (
        len(merged_results) == 0
        or retrieval_confidence.get("should_retry") is False
        and retrieval_confidence.get("score", 1.0) < settings.confidence_threshold
        and len(merged_results) == 0
    )

    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
    )

    prompt_hash = hashlib.md5(query_text.encode()).hexdigest()[:8]

    if is_knowledge_gap or not merged_results:
        # Knowledge gap: no usable results
        start = time.perf_counter()
        try:
            response = llm.invoke(
                [
                    SystemMessage(content=_SYSTEM_PROMPT),
                    HMsg(content=_GAP_PROMPT.format(question=query_text)),
                ]
            )
            response_text = response.content
        except Exception:
            response_text = (
                "I don't have enough information in my knowledge base to fully answer your question. "
                "Please contact a human support agent for assistance."
            )
        latency_ms = (time.perf_counter() - start) * 1000

        final_score = retrieval_confidence.get("score", 0.0)
        final_attempt = state.get("retrieval_attempt", 0)

        gap_event = log_knowledge_gap(
            run_id=run_id,
            final_attempt=final_attempt,
            final_score=final_score,
            reason=retrieval_confidence.get(
                "reason", "Retrieval confidence below threshold after max attempts"
            ),
        )
        llm_event = log_llm_call(
            run_id=run_id,
            agent="response_generator",
            model=settings.llm_model,
            prompt_hash=prompt_hash,
            input_tokens=0,
            output_tokens=0,
            latency_ms=latency_ms,
        )

        action_needed = _detect_action_needed(query_text)
        return {
            "response_text": response_text,
            "citations": [],
            "routed_to_agent": "response_generator",
            "action_needed": action_needed,
            "log_events": [gap_event, llm_event],
        }

    # Build context from merged results
    context_parts = []
    for i, doc in enumerate(merged_results):
        domain = doc.get("domain", "unknown")
        metadata = doc.get("metadata", {})
        title = metadata.get("title", metadata.get("source_file", f"Document {i + 1}"))
        source = metadata.get("source_file", title)
        content = doc.get("content", "")
        context_parts.append(f"[{i + 1}] Domain: {domain} | Source: {source}\n{content}")

    context = "\n\n---\n\n".join(context_parts)

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HMsg(content=_RESPONSE_PROMPT.format(question=query_text, context=context)),
    ]

    start = time.perf_counter()
    try:
        response = llm.invoke(messages)
        response_text = response.content
    except Exception:
        response_text = (
            "I apologize — I encountered an error while processing your request. "
            "Please try again or contact our support team directly."
        )
    latency_ms = (time.perf_counter() - start) * 1000

    # Build citations from merged results
    citations = [
        {
            "content": doc.get("content", "")[:300],
            "domain": doc.get("domain", "unknown"),
            "source": doc.get("metadata", {}).get("source_file", ""),
            "score": doc.get("score", 0.0),
            # Legacy fields for backwards compatibility
            "doc_id": doc.get("metadata", {}).get("doc_id", ""),
            "chunk_text": doc.get("content", "")[:300],
            "title": doc.get("metadata", {}).get("title", ""),
            "source_file": doc.get("metadata", {}).get("source_file", ""),
        }
        for doc in merged_results
    ]

    llm_event = log_llm_call(
        run_id=run_id,
        agent="response_generator",
        model=settings.llm_model,
        prompt_hash=prompt_hash,
        input_tokens=0,
        output_tokens=0,
        latency_ms=latency_ms,
    )
    response_event = log_agent_response(
        run_id=run_id,
        agent="response_generator",
        response_length=len(response_text),
        citation_count=len(citations),
    )

    # Detect whether tool action is needed based on query intent
    action_needed = _detect_action_needed(query_text)

    return {
        "response_text": response_text,
        "citations": citations,
        "routed_to_agent": "response_generator",
        "action_needed": action_needed,
        "log_events": [llm_event, response_event],
    }


_ACTION_KEYWORDS = (
    "status of my order",
    "order status",
    "where is my order",
    "track my order",
    "create a ticket",
    "open a ticket",
    "submit a ticket",
    "create a support ticket",
    "refund",
    "cancel my order",
)


def _detect_action_needed(query_text: str) -> bool:
    """Return True if the query contains keywords suggesting a tool action is needed."""
    lowered = query_text.lower()
    return any(kw in lowered for kw in _ACTION_KEYWORDS)
