"""Verify node: customer verification and HITL interrupt for unknown customers."""

from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from src.config import get_db_connection, llm
from src.state import State


class UserInput(BaseModel):
    identifier: str = Field(
        description=(
            "The customer's own identifier: a numeric customer ID, email address, "
            "or phone number. NOT an order ID or product name. "
            "Return an empty string if no customer identifier is present."
        )
    )


_structured_llm = llm.with_structured_output(UserInput)

_EXTRACT_SYSTEM = (
    "Extract the customer's own identifier from the message. "
    "A customer identifier is one of: "
    "(1) a numeric customer ID (e.g. 'my customer ID is 1' → '1'), "
    "(2) an email address (e.g. 'my email is x@y.com'), "
    "(3) a phone number (e.g. '+91-9876543210'). "
    "Do NOT return order IDs, product names, or anything else. "
    "If no customer identifier is present, return an empty string."
)


def get_customer_id_from_identifier(identifier: str) -> Optional[int]:
    """Resolve an identifier string to an integer customer ID via DB lookup."""
    if not identifier:
        return None

    identifier = identifier.strip()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if identifier.isdigit():
            # Validate the numeric ID actually exists in the DB
            cur.execute("SELECT id FROM customers WHERE id = ?", (int(identifier),))
        elif identifier.startswith("+"):
            cur.execute("SELECT id FROM customers WHERE phone = ?", (identifier,))
        elif "@" in identifier:
            cur.execute("SELECT id FROM customers WHERE email = ?", (identifier,))
        else:
            return None
        row = cur.fetchone()
    finally:
        conn.close()

    return row["id"] if row else None


def verify_info(state: State, config: RunnableConfig) -> dict:
    """
    Extract and verify the customer's identity from their messages.
    If already verified, pass through. If found in DB, set customer_id.
    If not found, return empty dict so should_interrupt routes to human_input.
    """
    if state.get("customer_id"):
        return {}

    try:
        messages = [SystemMessage(content=_EXTRACT_SYSTEM)] + list(state["messages"])
        extracted: UserInput = _structured_llm.invoke(messages)
        customer_id = get_customer_id_from_identifier(extracted.identifier)
    except Exception as e:
        print(f"verify_info: LLM extraction failed — {e}")
        customer_id = None

    if customer_id is None:
        # Add a verification prompt as an AIMessage so it appears in chat history.
        # Use a different message on retries (more than one HumanMessage already seen).
        human_count = sum(1 for m in state.get("messages", []) if isinstance(m, HumanMessage))
        if human_count > 1:
            prompt = (
                "We couldn't find an account with that information. "
                "Please try again with a valid **customer ID**, **email**, or **phone number**."
            )
        else:
            prompt = (
                "To look up your account, please provide your **customer ID**, "
                "**email address**, or **phone number**."
            )
        return {"messages": [AIMessage(content=prompt)]}

    # Confirm verification with a system message
    return {
        "customer_id": int(customer_id),
        "messages": [
            SystemMessage(content=f"Customer verified. Customer ID: {customer_id}.")
        ],
    }


def should_interrupt(state: State) -> str:
    """Route to 'continue' if customer is verified, else 'interrupt' for human input."""
    return "continue" if state.get("customer_id") else "interrupt"


def human_input(state: State, config: RunnableConfig) -> dict:
    """Pause execution and ask the human for their customer identifier."""
    user_response = interrupt(
        "Please provide your customer ID, email, or phone number."
    )
    return {"messages": [{"role": "user", "content": user_response}]}
