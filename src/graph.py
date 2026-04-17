"""Full graph assembly and compilation."""

import sqlite3
from pathlib import Path

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

DIRECT_RESPONSE_ROUTES = {"greeting"}

from src.agents.faq_agent import faq_agent
from src.agents.order_agent import order_agent
from src.agents.refund_agent import refund_agent
from src.agents.ticket_agent import ticket_agent
from src.nodes.hitl import hitl_check, hitl_route, human_approval
from src.nodes.quality import quality_checker, quality_route
from src.nodes.supervisor import supervisor
from src.nodes.verify import human_input, should_interrupt, verify_info
from src.state import State

# ── Agent node wrappers ────────────────────────────────────────────────────────
# Each create_react_agent is a compiled sub-graph. We wrap it so it receives
# the parent messages, runs its tool loop, and returns only the new messages.
#
# customer_id is injected as a SystemMessage so the LLM always knows which ID
# to pass to tools — agents must never decide this themselves.

def _agent_node(agent, state: State) -> dict:
    customer_id = state.get("customer_id")
    if not customer_id:
        print(f"_agent_node: blocked — customer_id is {customer_id!r}, verification must have failed")
        msg = "Customer identity is not verified. Please restart the conversation and provide your customer ID."
        return {
            "messages": [SystemMessage(content=msg)],
            "agent_response": "Customer identity is not verified.",
        }

    ctx = SystemMessage(
        content=(
            f"SECURITY CONTEXT: The verified customer_id for this session is {customer_id}. "
            f"You MUST pass customer_id={customer_id} to every tool call. "
            "Never use any other customer_id value."
        )
    )
    messages_with_ctx = [ctx] + list(state["messages"])
    result = agent.invoke({"messages": messages_with_ctx})
    # Slice off the injected ctx message so only the agent's new turns are stored.
    original_count = len(messages_with_ctx)
    new_messages = result["messages"][original_count:]
    last_ai = result["messages"][-1]
    return {"messages": new_messages, "agent_response": last_ai.content}


def order_agent_node(state: State, config: RunnableConfig) -> dict:
    """Run the order tracking agent."""
    return _agent_node(order_agent, state)


def refund_agent_node(state: State, config: RunnableConfig) -> dict:
    """Run the refund processing agent."""
    return _agent_node(refund_agent, state)


def ticket_agent_node(state: State, config: RunnableConfig) -> dict:
    """Run the support ticket agent."""
    return _agent_node(ticket_agent, state)


def faq_agent_node(state: State, config: RunnableConfig) -> dict:
    """Run the FAQ assistant agent."""
    return _agent_node(faq_agent, state)


# ── Graph construction ─────────────────────────────────────────────────────────

def _build_graph() -> StateGraph:
    graph = StateGraph(State)

    # Nodes
    graph.add_node("verify_info", verify_info)
    graph.add_node("human_input", human_input)
    graph.add_node("supervisor", supervisor)
    graph.add_node("order_agent", order_agent_node)
    graph.add_node("refund_agent", refund_agent_node)
    graph.add_node("ticket_agent", ticket_agent_node)
    graph.add_node("faq_agent", faq_agent_node)
    graph.add_node("quality_checker", quality_checker)
    graph.add_node("hitl_check", hitl_check)
    graph.add_node("human_approval", human_approval)

    # Edges
    graph.add_edge(START, "verify_info")

    graph.add_conditional_edges(
        "verify_info",
        should_interrupt,
        {"continue": "supervisor", "interrupt": "human_input"},
    )

    # human_input loops back to verify_info after the human provides their ID
    graph.add_edge("human_input", "verify_info")

    supervisor_edges = {route: END for route in DIRECT_RESPONSE_ROUTES}
    supervisor_edges.update({
        "order_agent": "order_agent",
        "refund_agent": "refund_agent",
        "ticket_agent": "ticket_agent",
        "faq_agent": "faq_agent",
    })
    graph.add_conditional_edges(
        "supervisor",
        lambda state: state["route_to"],
        supervisor_edges,
    )

    # All agents feed into the quality checker
    graph.add_edge("order_agent", "quality_checker")
    graph.add_edge("refund_agent", "quality_checker")
    graph.add_edge("ticket_agent", "quality_checker")
    graph.add_edge("faq_agent", "quality_checker")

    # Quality checker: pass → hitl_check, or loop back to the same agent
    graph.add_conditional_edges(
        "quality_checker",
        quality_route,
        {
            "pass": "hitl_check",
            "order_agent": "order_agent",
            "refund_agent": "refund_agent",
            "ticket_agent": "ticket_agent",
            "faq_agent": "faq_agent",
        },
    )

    # HITL check: escalate to human or go straight to END
    graph.add_conditional_edges(
        "hitl_check",
        hitl_route,
        {
            "end": END,
            "human_approval": "human_approval",
        },
    )

    graph.add_edge("human_approval", END)

    return graph


# SqliteSaver persists checkpoints across process restarts.
# Open the connection directly so we get a saver instance (not a context manager).
_CHECKPOINT_PATH = Path(__file__).parent.parent / "checkpoints.db"
_conn = sqlite3.connect(str(_CHECKPOINT_PATH), check_same_thread=False)
_checkpointer = SqliteSaver(_conn)
compiled_graph = _build_graph().compile(checkpointer=_checkpointer)
