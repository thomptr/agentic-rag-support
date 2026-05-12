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
from src.observability import langfuse_init


def _spanned(fn, name: str):
    """Wrap a graph node so its execution becomes a child span of the active
    invocation trace. Keeps span input/output tiny — graph state is huge."""

    def wrapped(state):
        with langfuse_init.span(
            name=f"node.{name}",
            input_payload={"current_node": state.get("current_node")},
        ) as sp:
            out = fn(state)
            if isinstance(out, dict):
                summary = {
                    "current_node": out.get("current_node"),
                    "action_needed": out.get("action_needed"),
                    "tool_calls": len(out.get("tool_calls") or []),
                }
                sp.update(output=summary)
            else:
                # Command(goto=...) and similar — record the routing decision.
                sp.update(output={"command": str(out)[:200]})
            return out

    wrapped.__name__ = f"spanned_{name}"
    return wrapped


def _build_graph():
    builder = StateGraph(SupportGraphState)

    # Pipeline nodes
    builder.add_node("supervisor", _spanned(supervisor, "supervisor"))
    builder.add_node("security_check", _spanned(security_check, "security_check"))
    builder.add_node("retrieval_planner", _spanned(retrieval_planner, "retrieval_planner"))
    builder.add_node("multi_retriever", _spanned(multi_retriever, "multi_retriever"))
    builder.add_node("confidence_check", _spanned(confidence_check, "confidence_check"))

    # Domain-specific response generators (replace the generic response_generator
    # on the main path; response_generator stays as the unknown-domain fallback).
    builder.add_node("billing_agent", _spanned(billing_agent, "billing_agent"))
    builder.add_node("technical_agent", _spanned(technical_agent, "technical_agent"))
    builder.add_node("account_agent", _spanned(account_agent, "account_agent"))
    builder.add_node("response_generator", _spanned(response_generator, "response_generator"))

    # Action path
    builder.add_node("action_planner", _spanned(action_planner, "action_planner"))
    builder.add_node("action_executor", _spanned(action_executor, "action_executor"))

    # Terminal / utility nodes
    builder.add_node("validate_response", _spanned(validate_response, "validate_response"))
    builder.add_node("fallback_handler", _spanned(fallback_handler, "fallback_handler"))
    builder.add_node("escalation_handler", _spanned(escalation_handler, "escalation_handler"))

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
