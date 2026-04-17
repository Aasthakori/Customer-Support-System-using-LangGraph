"""FAQ assistant agent."""

from langgraph.prebuilt import create_react_agent

from src.config import llm
from src.tools.faq_tools import search_knowledge_base

_SYSTEM_PROMPT = (
    "You are a customer support FAQ assistant. "
    "Answer common questions about store policies using the knowledge base. "
    "If you cannot find the answer, suggest the customer contact support directly."
)

faq_agent = create_react_agent(llm, tools=[search_knowledge_base], prompt=_SYSTEM_PROMPT)
