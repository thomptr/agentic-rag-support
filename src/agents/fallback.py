from src.graph.state import SupportGraphState
from src.observability.logger import log_agent_response


def fallback_handler(state: SupportGraphState) -> dict:
    query_text = state.get("query_text", "")
    run_id = state.get("run_id", "")

    response_text = (
        f'I wasn\'t able to confidently route your request: "{query_text}". '
        "Your query may span multiple topics or fall outside our current support categories. "
        "Please contact our support team directly and a specialist will be glad to help you."
    )

    response_event = log_agent_response(
        run_id=run_id,
        agent="fallback",
        response_length=len(response_text),
        citation_count=0,
    )

    return {
        "response_text": response_text,
        "citations": [],
        "routed_to_agent": "fallback_handler",
        "log_events": [response_event],
    }
