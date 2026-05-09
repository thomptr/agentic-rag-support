import hashlib
import time

from langchain_openai import ChatOpenAI

from src.config import settings
from src.graph.state import SupportGraphState
from src.observability.logger import log_agent_response, log_llm_call, log_retrieval
from src.rag.retriever import retrieve_documents

_ACCOUNT_SYSTEM_PROMPT = """You are an account management specialist for customer support.

Your responsibilities:
1. Handle login issues: password reset, login troubleshooting, locked account recovery.
2. Handle MFA: setup, troubleshooting, recovery codes, device changes.
3. Handle permissions: role management, access control, organization membership.
4. Handle security questions: setup, reset, best practices.
5. Escalate account takeover concerns: detect and flag unauthorized access reports immediately.

CRITICAL RULES:
- NEVER include passwords, account numbers, SSNs, or security question answers in responses.
- NEVER expose raw credentials or private user data of any kind.
- ALWAYS cite the source document(s) you used.
- If retrieved documents do not contain the answer, acknowledge the gap rather than guessing.
- For account takeover concerns, ALWAYS direct the user to our security team immediately.
"""

_TAKEOVER_KEYWORDS = frozenset(
    [
        "someone accessed",
        "unauthorized",
        "account compromised",
        "account stolen",
        "didn't make this change",
        "i didn't do",
        "hacked",
        "breached",
        "takeover",
        "unauthorized login",
        "suspicious login",
        "someone logged in",
        "not me",
        "account was accessed",
        "someone else",
        "suspicious activity",
        "compromised",
        "account was compromised",
    ]
)

_SENSITIVE_DATA_PATTERNS = [
    r"\b\d{3}-\d{2}-\d{4}\b",  # SSN pattern
    r"\bpassword\s*[:=]\s*\S+",  # password: value
    r"\bsecret\s*[:=]\s*\S+",  # secret: value
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # email (allowed in context, not sensitive)
]


def _is_takeover_query(query_text: str) -> bool:
    query_lower = query_text.lower()
    return any(kw in query_lower for kw in _TAKEOVER_KEYWORDS)


def account_agent(state: SupportGraphState) -> dict:
    query_text = state["query_text"]
    run_id = state["run_id"]

    is_takeover = _is_takeover_query(query_text)

    retrieval_start = time.perf_counter()
    docs = retrieve_documents(
        query=query_text,
        domain="account",
        run_id=run_id,
        agent="account_agent",
    )
    retrieval_elapsed_ms = (time.perf_counter() - retrieval_start) * 1000

    retrieval_event = log_retrieval(
        run_id=run_id,
        agent="account_agent",
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
        context = "No relevant documents found in the account knowledge base."

    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
    )

    from langchain_core.messages import HumanMessage as HMsg
    from langchain_core.messages import SystemMessage

    messages = [
        SystemMessage(content=_ACCOUNT_SYSTEM_PROMPT),
        HMsg(
            content=(
                f"Customer account query: {query_text}\n\n"
                f"Retrieved account knowledge base documents:\n\n{context}"
            )
        ),
    ]

    start = time.perf_counter()
    try:
        response = llm.invoke(messages)
        response_text = response.content
    except Exception:
        response_text = (
            "I apologize — I encountered an error while processing your account inquiry. "
            "Please contact our account support team directly for immediate assistance."
        )

    latency_ms = (time.perf_counter() - start) * 1000
    prompt_hash = hashlib.md5(query_text.encode()).hexdigest()[:8]

    llm_event = log_llm_call(
        run_id=run_id,
        agent="account_agent",
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

    escalation_metadata: dict = {}
    if is_takeover:
        escalation_prefix = (
            "⚠️ SECURITY ALERT: This appears to be an account takeover concern. "
            "Please contact our security team immediately at security@example.com or use "
            "the 'Report Security Incident' option in your account dashboard. "
            "Our security team responds within 2 business hours for active incidents.\n\n"
        )
        response_text = escalation_prefix + response_text
        escalation_metadata = {"escalation_flag": True, "escalation_reason": "account_takeover"}

        escalation_event = {
            "event_type": "escalation_triggered",
            "run_id": run_id,
            "agent": "account_agent",
            "reason": "account_takeover_keywords_detected",
        }
        llm_event_list = [llm_event, escalation_event]
    else:
        llm_event_list = [llm_event]

    response_event = log_agent_response(
        run_id=run_id,
        agent="account_agent",
        response_length=len(response_text),
        citation_count=len(citations),
    )

    result = {
        "response_text": response_text,
        "citations": citations,
        "retrieved_documents": docs,
        "log_events": [retrieval_event] + llm_event_list + [response_event],
    }
    if escalation_metadata:
        result["escalation_metadata"] = escalation_metadata

    return result
