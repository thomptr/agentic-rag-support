from src.graph.state import SupportGraphState

_DOMAIN_TO_NODE: dict[str, str] = {
    "billing": "billing_agent",
    "technical": "technical_agent",
    "account": "account_agent",
    "unknown": "fallback_handler",
}


def route_query(state: SupportGraphState) -> str:
    domain = state.get("classified_domain") or "unknown"
    return _DOMAIN_TO_NODE.get(domain, "fallback_handler")
