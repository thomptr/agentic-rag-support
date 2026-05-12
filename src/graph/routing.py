from src.graph.state import SupportGraphState


def route_supervisor(state: SupportGraphState) -> str:
    """Route from supervisor: classifiable queries go to security_check, unknown to fallback."""
    domains = state.get("classified_domains") or []
    if not domains or domains == ["unknown"]:
        return "fallback_handler"
    return "security_check"


def route_confidence_check(state: SupportGraphState) -> str:
    """Route from confidence_check: retry or proceed to a domain agent.

    After the domain-agents refactor, this no longer goes straight to a
    generic `response_generator`. Instead, it dispatches to one of the
    domain-specific agents (`billing_agent`, `technical_agent`,
    `account_agent`) based on the supervisor's classification, with
    `response_generator` reserved as the fallback when the domain is
    unknown or unclassifiable.
    """
    confidence = state.get("retrieval_confidence") or {}
    if confidence.get("should_retry", False):
        return "retrieval_planner"

    from src.agents.profiles import domain_to_agent

    domains = state.get("classified_domains") or []
    primary_domain = domains[0] if domains else "unknown"
    return domain_to_agent(primary_domain)


def route_domain_agent(state: SupportGraphState) -> str:
    """Route from a domain agent (or response_generator fallback): action_needed → action_planner."""
    if state.get("action_needed"):
        return "action_planner"
    return "validate_response"


# Backwards-compat alias for callers/tests still importing the old name.
route_response_generator = route_domain_agent
