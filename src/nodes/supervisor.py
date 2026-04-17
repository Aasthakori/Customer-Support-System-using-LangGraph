"""Supervisor node: intent classification and routing."""

from typing import Literal

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from src.config import llm
from src.state import State

_SYSTEM_PROMPT = (
    "You are a customer support supervisor. Read the customer's message and decide "
    "which agent should handle it. "
    "order_agent: order tracking and status queries. "
    "refund_agent: refund requests and eligibility checks. "
    "ticket_agent: complaints, issues, and support ticket creation. "
    "faq_agent: general questions about store policies (returns, shipping, payments, etc). "
    "Pick the single best agent."
)


class RouteDecision(BaseModel):
    route_to: Literal["order_agent", "refund_agent", "ticket_agent", "faq_agent", "greeting"]
    reasoning: str


_structured_llm = llm.with_structured_output(RouteDecision)


def supervisor(state: State, config: RunnableConfig) -> dict:
    """Classify customer intent and set route_to in state."""
    import re

    # Get the latest human message
    latest_human = None
    for msg in reversed(state["messages"]):
        if hasattr(msg, "type") and msg.type == "human":
            latest_human = msg.content
            break

    if latest_human:
        text = latest_human.strip().lower()
        # Check if message is verification-only (no real question)
        has_email = bool(re.search(r'\S+@\S+\.\S+', text))
        has_phone = bool(re.search(r'\+?\d{10,}', text))
        has_id_phrase = bool(re.search(r'(my\s+customer\s+id\s+is|my\s+email\s+is|my\s+phone\s+is)', text))
        word_count = len(text.split())

        is_verification_only = (
            (has_email or has_phone or has_id_phrase)
            and word_count < 12
            and "?" not in text
            and not any(q in text for q in ["status", "refund", "complaint", "policy", "how", "what", "when", "where", "why", "track"])
        )

        if is_verification_only:
            greeting = "You're verified! What can I help you with today? I can assist with order tracking, refund processing, filing a complaint, or answering common questions."
            return {
                "route_to": "greeting",
                "agent_response": greeting,
                "quality_passed": True,
                "messages": [AIMessage(content=greeting)],
            }

    messages = [SystemMessage(content=_SYSTEM_PROMPT)] + list(state["messages"])
    try:
        decision: RouteDecision = _structured_llm.invoke(messages)
        return {"route_to": decision.route_to}
    except Exception as e:
        print(f"supervisor: LLM routing failed ({e}), defaulting to faq_agent")
        return {"route_to": "faq_agent"}
