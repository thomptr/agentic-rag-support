from langgraph.graph import END, START, StateGraph

from src.agents.action_executor import action_executor
from src.agents.action_planner import action_planner
from src.agents.confidence_check import confidence_check
from src.agents.escalation_handler import escalation_handler
from src.agents.fallback import fallback_handler
from src.agents.multi_retriever import multi_retriever
from src.agents.response_generator import response_generator
from src.agents.retrieval_planner import retrieval_planner
from src.agents.security_check import security_check
from src.agents.supervisor import supervisor
from src.agents.validate_response import validate_response
from src.graph.routing import route_response_generator
from src.graph.state import SupportGraphState


def _build_graph():
    builder = StateGraph(SupportGraphState)

    builder.add_node("supervisor", supervisor)
    builder.add_node("security_check", security_check)
    builder.add_node("retrieval_planner", retrieval_planner)
    builder.add_node("multi_retriever", multi_retriever)
    builder.add_node("confidence_check", confidence_check)
    builder.add_node("response_generator", response_generator)
    builder.add_node("action_planner", action_planner)
    builder.add_node("action_executor", action_executor)
    builder.add_node("validate_response", validate_response)
    builder.add_node("fallback_handler", fallback_handler)
    builder.add_node("escalation_handler", escalation_handler)

    # supervisor returns Command(goto=...) — routes to security_check or fallback_handler
    builder.add_edge(START, "supervisor")

    # security_check returns Command(goto=...) — routes to retrieval_planner or escalation_handler

    # Main retrieval pipeline
    builder.add_edge("retrieval_planner", "multi_retriever")
    builder.add_edge("multi_retriever", "confidence_check")

    # confidence_check returns Command(goto=...) — routes to retrieval_planner or response_generator

    # After response_generator: branch to action path or directly to validate_response
    builder.add_conditional_edges(
        "response_generator",
        route_response_generator,
        {
            "action_planner": "action_planner",
            "validate_response": "validate_response",
        },
    )

    # Tool execution path
    builder.add_edge("action_planner", "action_executor")
    builder.add_edge("action_executor", "validate_response")

    builder.add_edge("validate_response", END)

    # Terminal nodes
    builder.add_edge("fallback_handler", END)
    builder.add_edge("escalation_handler", END)

    return builder.compile()


graph = _build_graph()
