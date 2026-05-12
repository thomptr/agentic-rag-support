from langgraph.graph import END, START, StateGraph

from src.agents.account_agent import account_agent
from src.agents.action_executor import action_executor
from src.agents.action_planner import action_planner
from src.agents.billing_agent import billing_agent
from src.agents.confidence_check import confidence_check
from src.agents.escalation_handler import escalation_handler
from src.agents.fallback import fallback_handler
from src.agents.multi_retriever import multi_retriever
from src.agents.response_generator import response_generator
from src.agents.retrieval_planner import retrieval_planner
from src.agents.security_check import security_check
from src.agents.supervisor import supervisor
from src.agents.technical_agent import technical_agent
from src.agents.validate_response import validate_response
from src.graph.routing import route_domain_agent
from src.graph.state import SupportGraphState


def _build_graph():
    builder = StateGraph(SupportGraphState)

    # Pipeline nodes
    builder.add_node("supervisor", supervisor)
    builder.add_node("security_check", security_check)
    builder.add_node("retrieval_planner", retrieval_planner)
    builder.add_node("multi_retriever", multi_retriever)
    builder.add_node("confidence_check", confidence_check)

    # Domain-specific response generators (replace the generic response_generator
    # on the main path; response_generator stays as the unknown-domain fallback).
    builder.add_node("billing_agent", billing_agent)
    builder.add_node("technical_agent", technical_agent)
    builder.add_node("account_agent", account_agent)
    builder.add_node("response_generator", response_generator)

    # Action path
    builder.add_node("action_planner", action_planner)
    builder.add_node("action_executor", action_executor)

    # Terminal / utility nodes
    builder.add_node("validate_response", validate_response)
    builder.add_node("fallback_handler", fallback_handler)
    builder.add_node("escalation_handler", escalation_handler)

    # supervisor returns Command(goto=...) — routes to security_check or fallback_handler
    builder.add_edge(START, "supervisor")
    # security_check returns Command(goto=...) — routes to retrieval_planner or escalation_handler

    # Retrieval pipeline (shared by all domain agents)
    builder.add_edge("retrieval_planner", "multi_retriever")
    builder.add_edge("multi_retriever", "confidence_check")
    # confidence_check returns Command(goto=...) — retries or dispatches to a domain
    # agent based on classified_domains[0] (via route_confidence_check + domain_to_agent).

    # Each domain agent + the generic fallback share the same downstream branch:
    # action_needed → action_planner → action_executor → validate_response,
    # otherwise → validate_response directly.
    for node in ("billing_agent", "technical_agent", "account_agent", "response_generator"):
        builder.add_conditional_edges(
            node,
            route_domain_agent,
            {
                "action_planner": "action_planner",
                "validate_response": "validate_response",
            },
        )

    builder.add_edge("action_planner", "action_executor")
    builder.add_edge("action_executor", "validate_response")

    builder.add_edge("validate_response", END)
    builder.add_edge("fallback_handler", END)
    builder.add_edge("escalation_handler", END)

    return builder.compile()


graph = _build_graph()
