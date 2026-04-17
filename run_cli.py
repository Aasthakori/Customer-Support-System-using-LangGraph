"""CLI test runner for individual agents and the full graph (Phase 2-4)."""

import argparse
import importlib
import sys
from uuid import uuid4

AGENTS = {
    "order":  ("src.agents.order_agent",  "order_agent"),
    "refund": ("src.agents.refund_agent", "refund_agent"),
    "ticket": ("src.agents.ticket_agent", "ticket_agent"),
    "faq":    ("src.agents.faq_agent",    "faq_agent"),
}


def run_agent(args: argparse.Namespace) -> None:
    module_path, attr = AGENTS[args.agent]
    mod = importlib.import_module(module_path)
    agent = getattr(mod, attr)

    print(f"\n{'='*60}")
    print(f"Agent   : {args.agent}")
    print(f"Message : {args.message}")
    print(f"{'='*60}\n")

    result = agent.invoke({"messages": [{"role": "user", "content": args.message}]})
    for message in result["messages"]:
        message.pretty_print()


def run_graph(args: argparse.Namespace) -> None:
    from langgraph.types import Command
    from src.graph import compiled_graph

    thread_id = args.thread_id or str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    print(f"\n{'='*60}")
    print(f"Mode      : graph")
    print(f"Thread ID : {thread_id}")
    print(f"Message   : {args.message}")
    print(f"{'='*60}\n")

    # Check if this thread has a pending interrupt to resume
    existing = compiled_graph.get_state(config)
    if existing.next:
        print(f"[Resuming thread — pending node: {existing.next}]")
        result = compiled_graph.invoke(Command(resume=args.message), config=config)
    else:
        input_state = {"messages": [{"role": "user", "content": args.message}]}
        result = compiled_graph.invoke(input_state, config=config)

    # Print all non-system messages
    for msg in result.get("messages", []):
        msg.pretty_print()

    # Detect interrupt
    if result.get("__interrupt__"):
        interrupts = result["__interrupt__"]
        print(f"\n[Graph paused]")
        for iv in interrupts:
            print(f"  Reason: {iv.value}")
        print(f"\nTo resume, run:")
        print(f"  python run_cli.py --graph --thread-id {thread_id} --message \"<response>\"")
    else:
        routed_to = result.get("route_to", "unknown")
        print(f"\n[Done — routed to: {routed_to}]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a customer-support agent or the full graph.")
    parser.add_argument("--graph", action="store_true", help="Use the full multi-agent graph")
    parser.add_argument(
        "--agent",
        choices=AGENTS.keys(),
        help="Which single agent to invoke: order, refund, ticket, faq",
    )
    parser.add_argument("--message", required=True, help="Customer message to send")
    parser.add_argument(
        "--thread-id",
        dest="thread_id",
        default=None,
        help="Reuse an existing thread ID (for multi-turn or resuming an interrupt)",
    )
    args = parser.parse_args()

    if args.graph:
        run_graph(args)
    elif args.agent:
        run_agent(args)
    else:
        parser.error("Specify either --graph or --agent <name>")


if __name__ == "__main__":
    main()
