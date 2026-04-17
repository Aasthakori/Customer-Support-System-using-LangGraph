"""Support ticket agent."""

from langgraph.prebuilt import create_react_agent

from src.config import llm
from src.tools.ticket_tools import create_ticket

_SYSTEM_PROMPT = (
    "You are a support ticket assistant. "
    "Create tickets for customer complaints and issues. "
    "Determine the appropriate category and priority from the customer's message. "
    "Always confirm the ticket ID after creation. "
    "IMPORTANT: Always read the customer_id from the SECURITY CONTEXT system message "
    "and pass it to every tool call. Never use any other customer_id."
)

ticket_agent = create_react_agent(llm, tools=[create_ticket], prompt=_SYSTEM_PROMPT)
