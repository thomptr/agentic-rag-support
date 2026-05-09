from langgraph.graph import END, START, StateGraph

from src.agents.account_agent import account_agent
from src.agents.billing_agent import billing_agent
from src.agents.fallback import fallback_handler
from src.agents.supervisor import supervisor
from src.agents.technical_agent import technical_agent
from src.agents.validate_response import validate_response
from src.graph.state import SupportGraphState


def _build_graph():
    builder = StateGraph(SupportGraphState)

    # classify_intent node
    builder.add_node("supervisor", supervisor)

    # route_to_worker destinations
    builder.add_node("billing_agent", billing_agent)
    builder.add_node("technical_agent", technical_agent)
    builder.add_node("account_agent", account_agent)
    builder.add_node("fallback_handler", fallback_handler)

    # validate_response node (per LangGraph Flow: worker → validate_response → END)
    builder.add_node("validate_response", validate_response)

    # Flow: START → supervisor (classify_intent)
    builder.add_edge(START, "supervisor")

    # supervisor returns Command(goto=...) — routing is handled by the Command object
    # Worker agents → validate_response → END
    builder.add_edge("billing_agent", "validate_response")
    builder.add_edge("technical_agent", "validate_response")
    builder.add_edge("account_agent", "validate_response")
    builder.add_edge("validate_response", END)

    # fallback bypasses validate_response (no RAG response to validate)
    builder.add_edge("fallback_handler", END)

    return builder.compile()


graph = _build_graph()
