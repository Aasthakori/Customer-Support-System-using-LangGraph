"""Refund processing agent."""

from langgraph.prebuilt import create_react_agent

from src.config import llm
from src.tools.refund_tools import check_refund_eligibility

_SYSTEM_PROMPT = (
    "You are a refund processing assistant. "
    "Check if the order is eligible for a refund. "
    "Report the eligibility status and amount to the customer. "
    "Do NOT process the refund yourself — it requires approval. "
    "IMPORTANT: Always read the customer_id from the SECURITY CONTEXT system message "
    "and pass it to every tool call. Never use any other customer_id."
)

refund_agent = create_react_agent(llm, tools=[check_refund_eligibility], prompt=_SYSTEM_PROMPT)
