import time

from langchain_openai import ChatOpenAI
from langgraph.types import Command
from pydantic import BaseModel

from src.config import settings
from src.graph.state import SupportGraphState
from src.observability.logger import log_routing_decision

_DOMAIN_TO_NODE = {
    "billing": "billing_agent",
    "technical": "technical_agent",
    "account": "account_agent",
    "unknown": "fallback_handler",
}

_VALID_DOMAINS = frozenset(("billing", "technical", "account", "unknown"))


class _DomainClassification(BaseModel):
    domain: str
    rationale: str


_CLASSIFY_PROMPT = """You are a customer support routing agent. Classify the customer query into exactly one domain.

Domains:
- billing: Charges, invoices, payments, refunds, subscriptions, pricing, cancellations
- technical: API errors, integrations, rate limits, webhooks, authentication errors, code issues
- account: Login, passwords, MFA, permissions, account security, profile changes
- unknown: Cannot be confidently classified into any domain above

When a query spans multiple domains, select the PRIMARY domain using these tiebreakers:
1. Security/account compromise concerns (hacking, unauthorized access) → always account, regardless of other topics
2. API errors, rate limits, or integration failures alongside account changes → technical (the API issue is the blocker)
3. Billing charges alongside account issues (no security concern, no API error) → billing
Classify as "unknown" only when genuinely unroutable.

Customer query: {query}

Respond with the domain and your reasoning for the classification."""


def supervisor(state: SupportGraphState) -> Command:
    query_text = state["query_text"]
    run_id = state["run_id"]

    domain = "unknown"
    rationale = "Unable to classify"

    try:
        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
        )
        structured_llm = llm.with_structured_output(_DomainClassification)
        prompt = _CLASSIFY_PROMPT.format(query=query_text)

        start = time.perf_counter()
        classification = structured_llm.invoke(prompt)
        _latency_ms = (time.perf_counter() - start) * 1000

        raw_domain = (classification.domain or "unknown").lower().strip()
        domain = raw_domain if raw_domain in _VALID_DOMAINS else "unknown"
        rationale = classification.rationale or "No rationale provided"

    except Exception as exc:
        domain = "unknown"
        rationale = f"Classification error: {exc}"

    goto = _DOMAIN_TO_NODE.get(domain, "fallback_handler")

    routing_event = log_routing_decision(
        run_id=run_id,
        query_text=query_text,
        classified_domain=domain,
        confidence_rationale=rationale,
        routed_to=goto,
    )

    return Command(
        goto=goto,
        update={
            "classified_domain": domain,
            "confidence_rationale": rationale,
            "routed_to_agent": goto,
            "log_events": [routing_event],
        },
    )
