# Customer Support System using LangGraph

Supervisor-worker agentic system using LangGraph — 4 ReAct agents, LLM-as-judge quality gate, human-in-the-loop refund approval, LangSmith tracing.

## Features

- **Supervisor routing** via Pydantic structured output dispatching to 4 ReAct subgraph agents
- **6 parameterized SQL tools** across a 5-table e-commerce database with customer-scoped query filters
- **LLM-as-judge quality gate** checking relevance, completeness, and tone with 2 retry cycles
- **Human-in-the-loop** refund approval using LangGraph interrupt — no refund executes without human authorization
- **Multi-method verification** — customer ID, email, or phone
- **Streamlit UI** with real-time agent activity sidebar and conversation history
- **SqliteSaver** checkpointing — state persists across restarts
- **LangSmith** tracing for full observability
- **Local LLM** — runs on Ollama (Qwen3 8B)

## Getting Started

```bash
git clone https://github.com/Aasthakori/Customer-Support-System-using-LangGraph.git
cd Customer-Support-System-using-LangGraph
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ollama pull qwen3:8b
cp .env.example .env.local  # add your LangSmith API key
python db/seed.py --force
streamlit run app.py
```

## Tech Stack

LangGraph · LangChain · Pydantic · SQLite · Streamlit · Ollama · LangSmith
