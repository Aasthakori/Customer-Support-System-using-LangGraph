"""Streamlit UI for the Multi-Agent Customer Support System."""

import sqlite3
import uuid

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

st.set_page_config(
    page_title="Customer Support",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Graph (cached so SqliteSaver is only initialised once per process) ─────────

@st.cache_resource
def get_graph():
    from src.graph import compiled_graph  # noqa: PLC0415
    return compiled_graph


# ── Session state helpers ──────────────────────────────────────────────────────

def _init_session():
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    if "display_messages" not in st.session_state:
        st.session_state.display_messages = []   # [{"role": "user"|"assistant", "content": str}]
    if "agent_info" not in st.session_state:
        st.session_state.agent_info = {}
    if "reject_mode" not in st.session_state:
        st.session_state.reject_mode = False


def _get_config() -> dict:
    return {"configurable": {"thread_id": st.session_state.thread_id}}


def _new_conversation():
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.display_messages = []
    st.session_state.agent_info = {}
    st.session_state.reject_mode = False


# ── Past conversations ─────────────────────────────────────────────────────────

def _get_past_thread_ids(limit: int = 20) -> list[str]:
    """
    Return up to `limit` distinct thread_ids from checkpoints.db,
    ordered by most-recently-updated first.
    Only considers root-namespace checkpoints (checkpoint_ns = '').
    """
    try:
        conn = sqlite3.connect("checkpoints.db")
        rows = conn.execute(
            """
            SELECT thread_id
            FROM checkpoints
            WHERE checkpoint_ns = ''
            GROUP BY thread_id
            ORDER BY MAX(checkpoint_id) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception as e:
        print(f"Failed to load past conversations: {e}")
        return []


def _preview_for_thread(thread_id: str) -> str:
    """
    Return a short preview string for a thread: the content of the first
    HumanMessage found in the checkpoint state.
    Falls back to 'Empty conversation' if none is found.
    """
    try:
        graph = get_graph()
        state = graph.get_state({"configurable": {"thread_id": thread_id}})
        for msg in state.values.get("messages", []):
            if isinstance(msg, HumanMessage) and msg.content:
                return str(msg.content)
    except Exception as e:
        print(f"Failed to load past conversations: {e}")
    return "Empty conversation"


def _display_messages_from_state(state_messages: list) -> list[dict]:
    """
    Convert a list of LangChain messages to display dicts, keeping only the
    LAST AIMessage per user turn so quality-check retry drafts are never shown.

    Strategy: buffer each AIMessage; flush the buffer only when the next
    HumanMessage (new turn) arrives or the list ends.
    """
    result: list[dict] = []
    pending_ai: str | None = None

    for msg in state_messages:
        if isinstance(msg, HumanMessage) and msg.content:
            if pending_ai is not None:
                result.append({"role": "assistant", "content": pending_ai})
                pending_ai = None
            result.append({"role": "user", "content": str(msg.content)})
        elif isinstance(msg, AIMessage) and msg.content:
            # Overwrite — a later AIMessage in the same turn replaces an earlier one
            pending_ai = str(msg.content)

    if pending_ai is not None:
        result.append({"role": "assistant", "content": pending_ai})

    return result


def _load_conversation(thread_id: str):
    """
    Switch the active thread to `thread_id` and repopulate
    st.session_state.display_messages from the checkpoint state.
    """
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    state = graph.get_state(config)

    messages = _display_messages_from_state(state.values.get("messages", []))

    st.session_state.thread_id = thread_id
    st.session_state.display_messages = messages
    st.session_state.agent_info = {
        "customer_id":         state.values.get("customer_id"),
        "route_to":            state.values.get("route_to"),
        "quality_passed":      state.values.get("quality_passed"),
        "correction_attempts": state.values.get("correction_attempts", 0),
        "escalation_needed":   state.values.get("escalation_needed"),
    }
    st.session_state.reject_mode = False


def _delete_conversation(thread_id: str):
    """Remove all checkpoint and write rows for `thread_id` from checkpoints.db."""
    conn = sqlite3.connect("checkpoints.db")
    conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
    conn.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))
    conn.commit()
    conn.close()


# ── Graph state inspection ─────────────────────────────────────────────────────

def _get_interrupt() -> tuple[str | None, object]:
    """Return (next_node, interrupt_value) if the graph is paused, else (None, None)."""
    graph = get_graph()
    try:
        state = graph.get_state(_get_config())
        if not state.next:
            return None, None
        next_node = state.next[0]
        interrupt_value = None
        for task in state.tasks or []:
            for intr in task.interrupts or []:
                interrupt_value = intr.value
                break
            if interrupt_value is not None:
                break
        return next_node, interrupt_value
    except Exception:
        return None, None


# ── Graph invocation ───────────────────────────────────────────────────────────

def _invoke(user_input: str, resume: bool = False) -> list[str]:
    """
    Invoke the graph with a new user message or a Command(resume=...).
    Returns a list of new AI message strings to display.
    """
    graph = get_graph()
    config = _get_config()

    # Record how many messages exist before invoke so we can diff afterwards
    try:
        prev_state = graph.get_state(config)
        prev_count = len(prev_state.values.get("messages", []))
    except Exception:
        prev_count = 0

    payload = Command(resume=user_input) if resume else {"messages": [HumanMessage(content=user_input)]}
    graph.invoke(payload, config)

    # Read updated state
    new_state = graph.get_state(config)
    all_msgs = new_state.values.get("messages", [])
    # Collect all new AI messages; only keep the last one — earlier ones are
    # quality-check retry drafts that the user should never see.
    new_ai_all = [
        m.content
        for m in all_msgs[prev_count:]
        if isinstance(m, AIMessage) and m.content
    ]
    new_ai = [new_ai_all[-1]] if new_ai_all else []

    # Persist agent metadata for the sidebar
    st.session_state.agent_info = {
        "customer_id":        new_state.values.get("customer_id"),
        "route_to":           new_state.values.get("route_to"),
        "quality_passed":     new_state.values.get("quality_passed"),
        "correction_attempts": new_state.values.get("correction_attempts", 0),
        "escalation_needed":  new_state.values.get("escalation_needed"),
    }

    return new_ai


# ── Sidebar ────────────────────────────────────────────────────────────────────

def _render_sidebar(next_node: str | None, interrupt_value: object):
    with st.sidebar:
        st.title("Agent Activity")

        # Thread / customer info
        tid = st.session_state.thread_id
        st.markdown(f"**Thread ID:** `{tid[:8]}…`")

        info = st.session_state.agent_info
        cid = info.get("customer_id")
        st.markdown(f"**Customer ID:** {cid if cid else '_Not verified_'}")

        route = info.get("route_to")
        if route:
            label = route.replace("_", " ").title()
            st.markdown(f"**Agent:** {label}")
            passed = info.get("quality_passed")
            attempts = info.get("correction_attempts", 0)
            quality_icon = "✓" if passed else "✗"
            st.markdown(f"**Quality:** {quality_icon} {'Passed' if passed else 'Failed'} ({attempts} {'retry' if attempts == 1 else 'retries'})")

        if info.get("escalation_needed"):
            st.markdown("**HITL:** Triggered — waiting for approval")

        st.divider()

        # ── Human-approval panel ──────────────────────────────────────────────
        if next_node == "human_approval" and isinstance(interrupt_value, dict):
            st.subheader("Approval Required")
            reason = interrupt_value.get("reason", "")
            st.markdown(f"**Reason:** {reason}")

            agent_resp = interrupt_value.get("agent_response", "") or ""
            st.text_area(
                "Agent's proposed response",
                value=agent_resp,
                height=150,
                disabled=True,
                key="approval_preview",
            )

            if not st.session_state.reject_mode:
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Approve", type="primary", use_container_width=True):
                        with st.spinner("Processing approval…"):
                            new_ai = _invoke("approved", resume=True)
                        for m in new_ai:
                            st.session_state.display_messages.append(
                                {"role": "assistant", "content": m}
                            )
                        st.rerun()
                with c2:
                    if st.button("Reject", use_container_width=True):
                        st.session_state.reject_mode = True
                        st.rerun()
            else:
                feedback = st.text_input("Rejection reason:", key="reject_feedback")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Submit", type="primary", use_container_width=True) and feedback:
                        with st.spinner("Sending feedback…"):
                            new_ai = _invoke(feedback, resume=True)
                        for m in new_ai:
                            st.session_state.display_messages.append(
                                {"role": "assistant", "content": m}
                            )
                        st.session_state.reject_mode = False
                        st.rerun()
                with c2:
                    if st.button("Cancel", use_container_width=True):
                        st.session_state.reject_mode = False
                        st.rerun()

        st.divider()

        # ── Past Conversations ────────────────────────────────────────────────
        past_ids = _get_past_thread_ids(limit=20)
        # Exclude the current thread so it isn't shown twice if it's new
        # (it's already reflected in the active chat area)
        if past_ids:
            st.subheader("Past Conversations")
            for tid in past_ids:
                preview = _preview_for_thread(tid)
                label = preview[:40] + ("…" if len(preview) > 40 else "")
                is_active = tid == st.session_state.thread_id
                btn_type = "primary" if is_active else "secondary"
                col_label, col_del = st.columns([9, 1])
                with col_label:
                    if st.button(
                        label,
                        key=f"past_{tid}",
                        use_container_width=True,
                        type=btn_type,
                    ):
                        _load_conversation(tid)
                        st.rerun()
                with col_del:
                    if st.button(
                        "✕",
                        key=f"del_{tid}",
                        use_container_width=True,
                        help="Delete this conversation",
                    ):
                        _delete_conversation(tid)
                        if tid == st.session_state.thread_id:
                            _new_conversation()
                        st.rerun()

        st.divider()
        if st.button("New Conversation", use_container_width=True):
            _new_conversation()
            st.rerun()


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    _init_session()

    # Read interrupt state once per rerun (shared by sidebar + body)
    next_node, interrupt_value = _get_interrupt()

    _render_sidebar(next_node, interrupt_value)

    st.title("Customer Support")

    # Render persisted conversation history
    for msg in st.session_state.display_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── State-driven input area ───────────────────────────────────────────────

    if next_node == "human_input":
        # The verification prompt is already in display_messages (added by verify_info
        # as an AIMessage before routing here) — no ephemeral rendering needed.
        user_id = st.chat_input("Enter your customer ID, email, or phone…")
        if user_id:
            st.session_state.display_messages.append({"role": "user", "content": user_id})
            with st.spinner("Verifying your identity…"):
                new_ai = _invoke(user_id, resume=True)
            for m in new_ai:
                st.session_state.display_messages.append({"role": "assistant", "content": m})
            st.rerun()

    elif next_node == "human_approval":
        # Approval UI is in the sidebar; disable the text input here
        st.info(
            "Your request requires human approval before it can be processed. "
            "Please use the **Approve / Reject** buttons in the sidebar."
        )
        st.chat_input("Waiting for approval in sidebar…", disabled=True)

    else:
        # Normal state — accept a new customer message
        user_input = st.chat_input("How can I help you today?")
        if user_input:
            st.session_state.display_messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

            with st.spinner(
                "Processing your request… our agents are working on it "
                "(this can take 1–3 minutes)"
            ):
                new_ai = _invoke(user_input, resume=False)

            # Check if the graph paused again after this invoke
            next_after, _ = _get_interrupt()

            if next_after == "human_input":
                # Verification required — persist the prompt AIMessage from the graph
                # then rerun so the chat history renders it before showing the input box.
                for m in new_ai:
                    st.session_state.display_messages.append(
                        {"role": "assistant", "content": m}
                    )
                st.rerun()
            else:
                # Show whatever the agent replied with
                for m in new_ai:
                    st.session_state.display_messages.append(
                        {"role": "assistant", "content": m}
                    )
                    with st.chat_message("assistant"):
                        st.markdown(m)

                # Always rerun so the sidebar reflects updated agent_info
                # (customer_id, agent route, quality status) from this invoke.
                st.rerun()


if __name__ == "__main__":
    main()
