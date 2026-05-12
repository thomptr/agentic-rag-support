import time

from langchain_openai import ChatOpenAI
from langgraph.types import Command
from pydantic import BaseModel

from src.config import settings
from src.graph.state import SupportGraphState
from src.observability import langfuse_init
from src.observability.logger import log_routing_decision

_VALID_DOMAINS = frozenset(("billing", "technical", "account"))


class _DomainClassification(BaseModel):
    domains: list[str]
    rationale: str


_CLASSIFY_PROMPT = """You are a customer support routing agent. Classify the customer query into one or more domains.

Domains:
- billing: Charges, invoices, payments, refunds, subscriptions, pricing, cancellations, plan changes
- technical: API errors, integrations, rate limits, webhooks, authentication errors, SDK issues, code issues
- account: Login, passwords, MFA, permissions, account security, profile changes, team management, data export

Instructions:
- A query may span multiple domains — return ALL applicable domains
- Return ["unknown"] ONLY when the query is genuinely unroutable to any domain above
- Order domains by relevance (most relevant first)

Customer query: {query}

Respond with the list of domains and your reasoning."""


def supervisor(state: SupportGraphState) -> Command:
    query_text = state["query_text"]
    run_id = state["run_id"]

    domains = ["unknown"]
    rationale = "Unable to classify"

    try:
        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
        )
        structured_llm = llm.with_structured_output(_DomainClassification)
        prompt = _CLASSIFY_PROMPT.format(query=query_text)

        start = time.perf_counter()
        with langfuse_init.generation(
            name="supervisor.classify_domain",
            model=settings.llm_model,
            input_payload=prompt,
        ) as gen:
            classification = structured_llm.invoke(prompt)
            gen.update(
                output={
                    "domains": classification.domains,
                    "rationale": classification.rationale,
                }
            )
        _latency_ms = (time.perf_counter() - start) * 1000

        raw_domains = [d.lower().strip() for d in (classification.domains or [])]
        valid = [d for d in raw_domains if d in _VALID_DOMAINS]
        domains = valid if valid else ["unknown"]
        rationale = classification.rationale or "No rationale provided"

    except Exception as exc:
        domains = ["unknown"]
        rationale = f"Classification error: {exc}"

    is_unknown = domains == ["unknown"]
    goto = "fallback_handler" if is_unknown else "security_check"

    # Keep backwards-compatible classified_domain for legacy consumers
    primary_domain = domains[0] if domains else "unknown"

    routing_event = log_routing_decision(
        run_id=run_id,
        query_text=query_text,
        classified_domain=primary_domain,
        confidence_rationale=rationale,
        routed_to=goto,
    )

    return Command(
        goto=goto,
        update={
            "classified_domain": primary_domain,
            "classified_domains": domains,
            "confidence_rationale": rationale,
            "current_node": goto,
            "log_events": [routing_event],
        },
    )
