import hashlib
import time

from langchain_openai import ChatOpenAI

from src.config import settings
from src.graph.state import SupportGraphState
from src.observability.logger import log_agent_response, log_llm_call, log_retrieval
from src.rag.retriever import retrieve_documents

_BILLING_SYSTEM_PROMPT = """You are a billing specialist for customer support.

Your responsibilities:
1. Retrieve & cite: Ground ALL answers in retrieved pricing, invoice, and cancellation documents. Never fabricate policy details.
2. Check subscription status: For subscription-related queries, explain status using retrieved content.
3. Explain charges: Break down charges using retrieved pricing/invoice documentation.
4. Determine refund eligibility: Reason over refund criteria from retrieved content and state eligibility with justification.
5. Escalate payment disputes: Detect dispute/chargeback queries and include escalation instructions from retrieved content (e.g., "this requires human review").

Rules:
- ALWAYS cite the source document(s) you used
- If retrieved documents do not contain the answer, clearly acknowledge the gap rather than guessing
- For billing disputes exceeding $500 or suspected fraud, state that a human billing specialist will be needed
"""


def billing_agent(state: SupportGraphState) -> dict:
    query_text = state["query_text"]
    run_id = state["run_id"]

    retrieval_start = time.perf_counter()
    docs = retrieve_documents(
        query=query_text,
        domain="billing",
        run_id=run_id,
        agent="billing_agent",
    )
    retrieval_elapsed_ms = (time.perf_counter() - retrieval_start) * 1000

    retrieval_event = log_retrieval(
        run_id=run_id,
        agent="billing_agent",
        query=query_text,
        top_k=5,
        results=[
            {
                "doc_id": d["metadata"].get("doc_id", ""),
                "score": d["score"],
                "preview": d["content"][:100],
            }
            for d in docs
        ],
        elapsed_ms=retrieval_elapsed_ms,
    )

    if docs:
        context = "\n\n---\n\n".join(
            f"[Source: {d['metadata'].get('title', 'Unknown')} | {d['metadata'].get('source_file', '')}]\n{d['content']}"
            for d in docs
        )
    else:
        context = "No relevant documents found in the billing knowledge base."

    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
    )

    from langchain_core.messages import HumanMessage as HMsg
    from langchain_core.messages import SystemMessage

    messages = [
        SystemMessage(content=_BILLING_SYSTEM_PROMPT),
        HMsg(
            content=(
                f"Customer query: {query_text}\n\n"
                f"Retrieved billing knowledge base documents:\n\n{context}"
            )
        ),
    ]

    start = time.perf_counter()
    try:
        response = llm.invoke(messages)
        response_text = response.content
    except Exception:
        response_text = (
            "I apologize — I encountered an error while processing your billing inquiry. "
            "Please contact our billing support team directly for immediate assistance."
        )

    latency_ms = (time.perf_counter() - start) * 1000
    prompt_hash = hashlib.md5(query_text.encode()).hexdigest()[:8]

    llm_event = log_llm_call(
        run_id=run_id,
        agent="billing_agent",
        model=settings.llm_model,
        prompt_hash=prompt_hash,
        input_tokens=0,
        output_tokens=0,
        latency_ms=latency_ms,
    )

    citations = [
        {
            "doc_id": d["metadata"].get("doc_id", ""),
            "chunk_text": d["content"][:300],
            "score": d["score"],
            "title": d["metadata"].get("title", ""),
            "source_file": d["metadata"].get("source_file", ""),
        }
        for d in docs
    ]

    response_event = log_agent_response(
        run_id=run_id,
        agent="billing_agent",
        response_length=len(response_text),
        citation_count=len(citations),
    )

    return {
        "response_text": response_text,
        "citations": citations,
        "retrieved_documents": docs,
        "log_events": [retrieval_event, llm_event, response_event],
    }
