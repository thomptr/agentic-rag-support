from src.graph.state import SupportGraphState


def route_supervisor(state: SupportGraphState) -> str:
    """Route from supervisor: classifiable queries go to security_check, unknown to fallback."""
    domains = state.get("classified_domains") or []
    if not domains or domains == ["unknown"]:
        return "fallback_handler"
    return "security_check"


def route_confidence_check(state: SupportGraphState) -> str:
    """Route from confidence_check: retry or proceed to response_generator."""
    confidence = state.get("retrieval_confidence") or {}
    if confidence.get("should_retry", False):
        return "retrieval_planner"
    return "response_generator"


def route_response_generator(state: SupportGraphState) -> str:
    """Route from response_generator: action needed → action_planner, else → validate_response."""
    if state.get("action_needed"):
        return "action_planner"
    return "validate_response"
