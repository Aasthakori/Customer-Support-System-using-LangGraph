# CLAUDE.md — Multi-Agent Customer Support System

## Project Overview
A LangGraph multi-agent customer support system for e-commerce. Forked concept from FareedKhan-dev/Multi-Agent-AI-System, rebuilt from scratch with a new domain, new schema, new agents, and production patterns.

## Tech Stack
- **LLM:** Ollama + qwen3:8b (local, free) via `langchain-ollama` (`ChatOllama`)
- **Framework:** LangGraph StateGraph
- **Database:** SQLite (file-based, NOT in-memory)
- **UI:** Streamlit (Phase 5)
- **Checkpointing:** SqliteSaver (langgraph-checkpoint-sqlite)
- **Python:** 3.12+

## Critical Constraints
- **8GB RAM MacBook Air** — LLM inference is slow (5-25s per call depending on output length). Minimize unnecessary LLM calls.
- **Zero API costs** — everything runs locally. No OpenAI, no Together AI, no external APIs.
- **Model name in Ollama:** `qwen3:8b` — use this exact string in ChatOllama(model=...).
- **Thinking mode:** qwen3:8b has a thinking/reasoning step enabled by default. Disable it in code to reduce latency.
- **Ollama version:** v0.17.6+ required.
- **Fallback models (in order):** qwen3:4b, glm4:9b, llama3.1:8b

## Project Structure
```
multi-agent-customer-support/
├── CLAUDE.md
├── requirements.txt
├── .env                    # minimal — only LANGSMITH_TRACING=false
├── db/
│   ├── schema.sql          # CREATE TABLE statements
│   ├── seed.py             # Faker-based seed data generator
│   └── customer_support.db # generated SQLite file (gitignored)
├── src/
│   ├── __init__.py
│   ├── config.py           # LLM init, DB connection, constants
│   ├── state.py            # State TypedDict
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── order_tools.py
│   │   ├── refund_tools.py
│   │   ├── ticket_tools.py
│   │   └── faq_tools.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── order_agent.py
│   │   ├── refund_agent.py
│   │   ├── ticket_agent.py
│   │   └── faq_agent.py
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── hitl.py         # HITL escalation check and human approval
│   │   ├── verify.py       # customer verification + HITL
│   │   ├── supervisor.py   # intent classification + routing
│   │   └── quality.py      # quality checker + retry logic
│   └── graph.py            # full graph assembly + compilation
├── app.py                  # Streamlit UI (Phase 5)
├── run_cli.py              # CLI test runner (Phase 2-4)
└── tests/
    └── test_tools.py       # direct tool tests (no LLM needed)
```

## Architecture (Graph Flow)
```
[START] → [verify_info] → conditional:
  ├── found → [supervisor] → conditional:
  │   ├── [order_agent]
  │   ├── [refund_agent]  
  │   ├── [ticket_agent]
  │   └── [faq_agent]
  │   → [quality_checker] → conditional:
  │       ├── passed → [hitl_check] → conditional:
  │       │   ├── no escalation → [respond] → [END]
  │       │   └── escalation → [human_approval] → interrupt() → [respond] → [END]
  │       └── failed (max 2) → [back to agent] (cycle)
  └── not found → [human_input] → interrupt() → [verify_info] (loop)
```

## State Schema
```python
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    customer_id: Optional[int]
    route_to: Optional[str]           # "order_agent" | "refund_agent" | "ticket_agent" | "faq_agent"
    agent_response: Optional[str]
    quality_passed: bool
    correction_attempts: int
    escalation_needed: bool
    remaining_steps: RemainingSteps
```

## Database Schema (5 tables)
- customers (id, name, email, phone, tier: bronze/silver/gold/platinum, created_at)
- products (id, name, category, price, stock, description)
- orders (id, customer_id, product_id, quantity, total, status: pending/processing/shipped/delivered/cancelled/returned, order_date, delivery_date)
- tickets (id, customer_id, order_id, category, priority, status, description, created_at)
- refunds (id, order_id, amount, reason, status: pending/approved/rejected/processed, created_at)

## Key Rules
1. **ALL SQL queries use parameterized queries** (`?` placeholders). NEVER f-string interpolation.
2. **One file = one responsibility.** Tools in tools/, agents in agents/, nodes in nodes/.
3. **Every tool function has a docstring** — the LLM reads these to decide which tool to call.
4. **Structured output via Pydantic** for supervisor routing (not tool calls, not free text).
5. **Max 2 quality check retries** — prevent infinite loops.
6. **HITL triggers:** all eligible refunds OR correction_attempts >= 2 failed quality retries.
7. **SqliteSaver for checkpointing** — NOT MemorySaver.
8. **Test each component in isolation before integrating.** Tools first, then agents, then graph.

## Build Phases
- Phase 1: Scaffold + DB + seed data (no LLM)
- Phase 2: Config + tools + agents (needs Ollama running)
- Phase 3: Supervisor + graph assembly
- Phase 4: Quality checker + HITL
- Phase 5: Streamlit UI
