from src.graph.state import SupportGraphState
from src.observability.logger import log_agent_response, log_escalation_triggered

_ESCALATION_RESPONSE = (
    "⚠️ SECURITY ALERT: This appears to require immediate attention from our security team. "
    "Please contact our security team directly at security@example.com or use the "
    "'Report Security Incident' option in your account dashboard. "
    "Our security team responds within 2 business hours for active incidents. "
    "For your safety, do not share account credentials or sensitive information here."
)


def escalation_handler(state: SupportGraphState) -> dict:
    """Terminal node for security-escalated queries.

    Produces a deterministic security-team-routing response without invoking retrieval
    or the response-generator LLM. Emits an `escalation_triggered` log event capturing
    the originating policy signal for audit / false-positive review.
    """
    run_id = state["run_id"]
    signals = state.get("security_signals") or []
    reason = state.get("escalation_reason") or "policy_signal"

    primary = signals[0] if signals else {"name": reason, "matched_pattern": ""}

    escalation_event = log_escalation_triggered(
        run_id=run_id,
        signal_name=primary.get("name", reason),
        matched_pattern=primary.get("matched_pattern", ""),
        reason=reason,
        agent="escalation_handler",
    )
    response_event = log_agent_response(
        run_id=run_id,
        agent="escalation_handler",
        response_length=len(_ESCALATION_RESPONSE),
        citation_count=0,
    )

    return {
        "response_text": _ESCALATION_RESPONSE,
        "citations": [],
        "current_node": "escalation_handler",
        "log_events": [escalation_event, response_event],
    }
