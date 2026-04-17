"""Quality checker node: evaluate agent responses and trigger retries."""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from src.config import MAX_CORRECTION_ATTEMPTS, llm
from src.state import State


class QualityResult(BaseModel):
    relevant: bool
    complete: bool
    appropriate_tone: bool
    passed: bool
    critique: str


_structured_llm = llm.with_structured_output(QualityResult)

_QUALITY_SYSTEM = (
    "You are a quality checker for customer support responses. "
    "Evaluate if the agent's response adequately addresses the customer's query. "
    "Check: (1) Is it relevant to what was asked? "
    "(2) If an action was needed (refund, ticket, lookup), was it completed or explained? "
    "(3) Is the tone professional and helpful? "
    "Be lenient — if the response is reasonable, pass it."
)


def quality_checker(state: State, config: RunnableConfig) -> dict:
    """Evaluate the agent response and decide pass/fail."""
    agent_response = state.get("agent_response")

    # Auto-fail if no response was generated
    if not agent_response:
        attempts = state.get("correction_attempts", 0) + 1
        return {
            "quality_passed": False,
            "correction_attempts": attempts,
            "messages": [
                SystemMessage(
                    content="Quality check failed: No response generated. Please regenerate your response addressing this feedback."
                )
            ],
        }

    # Find the last human message as the original customer query
    customer_query = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            customer_query = msg.content
            break

    prompt = (
        f"Customer query: {customer_query}\n\n"
        f"Agent response: {agent_response}"
    )

    try:
        result: QualityResult = _structured_llm.invoke(
            [SystemMessage(content=_QUALITY_SYSTEM), HumanMessage(content=prompt)]
        )
    except Exception as e:
        print(f"quality_checker: LLM evaluation failed ({e}), failing open")
        return {"quality_passed": True, "critique": ""}

    if result.passed:
        return {"quality_passed": True}

    attempts = state.get("correction_attempts", 0) + 1
    return {
        "quality_passed": False,
        "correction_attempts": attempts,
        "messages": [
            SystemMessage(
                content=(
                    f"Quality check failed: {result.critique}. "
                    "Please regenerate your response addressing this feedback."
                )
            )
        ],
    }


def quality_route(state: State) -> str:
    """Route after quality check: pass through or loop back to the same agent."""
    if state.get("quality_passed"):
        return "pass"
    if state.get("correction_attempts", 0) >= MAX_CORRECTION_ATTEMPTS:
        # Give up after 2 retries — let it through
        return "pass"
    return state["route_to"]
