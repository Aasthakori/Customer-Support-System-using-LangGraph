"""HITL (Human-In-The-Loop) nodes: escalation check and human approval."""

from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from src.config import MAX_CORRECTION_ATTEMPTS
from src.state import State
from src.tools.refund_tools import VALID_REASONS, process_refund


def _refund_was_eligible(state: State) -> bool:
    """
    Return True only if the MOST RECENT check_refund_eligibility ToolMessage
    indicates eligibility.

    We reverse-iterate so that a later ineligible check in the same conversation
    correctly overrides an earlier eligible one — preventing stale eligibility
    from a previous query from triggering HITL for a new, ineligible request.
    """
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, ToolMessage) and getattr(msg, "name", None) == "check_refund_eligibility":
            content = msg.content or ""
            return "is eligible for a refund" in content.lower()
    return False


def hitl_check(state: State, config: RunnableConfig) -> dict:
    """Determine whether human approval is required before sending the response."""
    needs_human = False

    route_to = state.get("route_to", "")
    correction_attempts = state.get("correction_attempts", 0)

    # Condition 1: refund agent only needs approval when the order IS eligible.
    # Skip HITL when the agent denies the refund (order not found, wrong status, etc.).
    if route_to == "refund_agent" and _refund_was_eligible(state):
        needs_human = True

    # Condition 2: quality checker exhausted its retry budget
    if correction_attempts >= MAX_CORRECTION_ATTEMPTS:
        needs_human = True

    return {"escalation_needed": needs_human}


def hitl_route(state: State) -> str:
    """Route to human approval or straight to end."""
    if state.get("escalation_needed"):
        return "human_approval"
    return "end"


def human_approval(state: State, config: RunnableConfig) -> dict:
    """Interrupt execution and wait for a human reviewer to approve or reject."""
    summary = {
        "agent_response": state.get("agent_response"),
        "route_to": state.get("route_to"),
        "reason": (
            "Refund requires human approval"
            if state.get("route_to") == "refund_agent"
            else f"Quality retries exhausted ({state.get('correction_attempts', 0)})"
        ),
    }

    decision = interrupt(summary)

    if isinstance(decision, str) and decision.strip().lower() in ("approved", "approve"):
        # For refund approvals: now actually process the refund
        if state.get("route_to") == "refund_agent":
            # customer_id is set by verify_info and always present at this point.
            customer_id = state.get("customer_id")
            if not customer_id:
                return {
                    "messages": [
                        SystemMessage(content="Error: cannot process refund — customer identity is missing from session.")
                    ]
                }

            # Extract order_id from the check_refund_eligibility tool call arguments
            order_id = None
            for msg in state["messages"]:
                if hasattr(msg, "tool_calls"):
                    for tc in (msg.tool_calls or []):
                        if tc.get("name") == "check_refund_eligibility":
                            order_id = tc.get("args", {}).get("order_id")
                            break
                if order_id is not None:
                    break

            # Extract reason from the most recent human message; default to changed_mind
            reason = "changed_mind"
            for msg in reversed(state["messages"]):
                if hasattr(msg, "type") and msg.type == "human":
                    text = msg.content.lower()
                    for r in VALID_REASONS:
                        if r.replace("_", " ") in text or r in text:
                            reason = r
                            break
                    break

            if order_id is not None:
                refund_result = process_refund.invoke({
                    "order_id": order_id,
                    "reason": reason,
                    "customer_id": customer_id,
                })
                return {
                    "messages": [
                        SystemMessage(content=f"Refund processed after human approval:\n{refund_result}")
                    ]
                }

        # Non-refund approval: pass through
        return {}

    # Rejection: feed feedback back into the cycle
    return {
        "messages": [
            SystemMessage(
                content=f"Human reviewer feedback: {decision}. Please revise your response."
            )
        ],
        "quality_passed": False,
        "correction_attempts": 0,
        "escalation_needed": False,
    }
