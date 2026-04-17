"""Central configuration: DB connection, LLM init, and shared constants."""

import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

# Load .env.local first (real credentials, gitignored); fall back to .env (placeholders).
_env_local = Path(__file__).parent.parent / ".env.local"
if _env_local.exists():
    load_dotenv(_env_local)
else:
    load_dotenv()

from langchain_ollama import ChatOllama

# ── Paths ─────────────────────────────────────────────────────────────────────

_default_db = str(Path(__file__).parent.parent / "db" / "customer_support.db")
DB_PATH = Path(os.getenv("DB_PATH", _default_db))

# ── LLM ──────────────────────────────────────────────────────────────────────

# think=False disables qwen3:8b's reasoning step, cutting latency significantly.
# Override MODEL_NAME in .env to switch to a fallback model without code changes.
MODEL_NAME = os.getenv("MODEL_NAME", "qwen3-nothink")
llm = ChatOllama(model=MODEL_NAME, temperature=0, think=False)

# ── Business constants ────────────────────────────────────────────────────────

REFUND_WINDOW_DAYS = 30          # Orders delivered more than this many days ago are ineligible
MAX_CORRECTION_ATTEMPTS = 2      # Quality checker retries before forcing a pass

# ── Database ──────────────────────────────────────────────────────────────────

def get_db_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row_factory set to sqlite3.Row.

    row_factory is required so callers can access columns by name (row["field"]).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
