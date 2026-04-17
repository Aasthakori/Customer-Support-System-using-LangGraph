"""Order tracking agent."""

from langgraph.prebuilt import create_react_agent

from src.config import llm
from src.tools.order_tools import lookup_customer_orders, lookup_order

_SYSTEM_PROMPT = (
    "You are an order tracking assistant. "
    "Use your tools to look up order information. "
    "Always provide the order status, product name, and expected delivery date when available. "
    "If the customer doesn't specify an order ID, ask for it. "
    "IMPORTANT: Always read the customer_id from the SECURITY CONTEXT system message "
    "and pass it to every tool call. Never use any other customer_id."
)

order_agent = create_react_agent(llm, tools=[lookup_order, lookup_customer_orders], prompt=_SYSTEM_PROMPT)
