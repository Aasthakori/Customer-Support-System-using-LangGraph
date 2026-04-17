"""LangGraph state definition for the customer support graph."""

from typing import Annotated, Optional

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from langgraph.managed.is_last_step import RemainingSteps
from typing_extensions import TypedDict


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    customer_id: Optional[int]
    route_to: Optional[str]          # "order_agent" | "refund_agent" | "ticket_agent" | "faq_agent"
    agent_response: Optional[str]
    quality_passed: bool
    correction_attempts: int
    escalation_needed: bool
    remaining_steps: RemainingSteps


def initial_state() -> dict:
    """Return a dict of default values for non-message state fields.

    Use this when constructing the first graph input so that nodes that
    read quality_passed, correction_attempts, or escalation_needed before
    those fields are first written always get a defined value.
    """
    return {
        "quality_passed": False,
        "correction_attempts": 0,
        "escalation_needed": False,
    }
