"""Phase 1 + Phase 2 tests — no LLM required."""

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure the project root is on sys.path so `src` is importable
# regardless of which directory the test is launched from.
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Tool imports for Phase 2 tests (called directly, no LLM)
from src.tools.order_tools import lookup_customer_orders, lookup_order
from src.tools.refund_tools import check_refund_eligibility, process_refund
from src.tools.ticket_tools import create_ticket
from src.tools.faq_tools import search_knowledge_base

DB_PATH = Path(__file__).parent.parent / "db" / "customer_support.db"


def run_seed() -> None:
    seed_script = Path(__file__).parent.parent / "db" / "seed.py"
    result = subprocess.run(
        [sys.executable, str(seed_script), "--force"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("seed.py STDOUT:", result.stdout)
        print("seed.py STDERR:", result.stderr)
        raise RuntimeError("seed.py failed")
    print(result.stdout.strip())


@pytest.fixture(scope="session", autouse=True)
def reset_db():
    """Reset the database to a clean known state once per test session."""
    run_seed()


@pytest.fixture
def cur():
    """Provide a sqlite3 Cursor with FK enforcement for Phase 1 DB tests."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON")
    yield c
    conn.close()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── row count tests ───────────────────────────────────────────────────────────

def test_row_counts(cur: sqlite3.Cursor) -> None:
    counts = {}
    for table, expected in [
        ("customers", 20),
        ("products", 50),
        ("orders", 80),
        ("tickets", 15),
        ("refunds", 10),
    ]:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        n = cur.fetchone()[0]
        counts[table] = n
        assert n == expected, f"{table}: expected {expected}, got {n}"
    print("  row counts      :", counts)


# ── status distribution tests ─────────────────────────────────────────────────

def test_status_distributions(cur: sqlite3.Cursor) -> None:
    # Orders should have all 6 statuses represented
    cur.execute("SELECT status, COUNT(*) as n FROM orders GROUP BY status ORDER BY status")
    order_dist = {row["status"]: row["n"] for row in cur.fetchall()}
    assert len(order_dist) > 1, "orders have only one status — seeding is broken"
    print("  order statuses  :", order_dist)

    # Tickets should span multiple priorities
    cur.execute("SELECT priority, COUNT(*) as n FROM tickets GROUP BY priority ORDER BY priority")
    prio_dist = {row["priority"]: row["n"] for row in cur.fetchall()}
    print("  ticket priority :", prio_dist)

    # Refunds should have multiple statuses
    cur.execute("SELECT status, COUNT(*) as n FROM refunds GROUP BY status ORDER BY status")
    refund_dist = {row["status"]: row["n"] for row in cur.fetchall()}
    print("  refund statuses :", refund_dist)


# ── edge case tests ───────────────────────────────────────────────────────────

def test_high_value_orders(cur: sqlite3.Cursor) -> None:
    cur.execute("SELECT COUNT(*) FROM orders WHERE total > 5000")
    n = cur.fetchone()[0]
    assert n > 0, "no orders with total > 5000"
    print(f"  orders > ₹5000  : {n}")


def test_delivery_timing(cur: sqlite3.Cursor) -> None:
    cur.execute(
        """
        SELECT
            SUM(CASE WHEN CAST(julianday(delivery_date) - julianday(order_date) AS INTEGER) <= 30
                     THEN 1 ELSE 0 END) AS within_30,
            SUM(CASE WHEN CAST(julianday(delivery_date) - julianday(order_date) AS INTEGER) > 30
                     THEN 1 ELSE 0 END) AS outside_30
        FROM orders
        WHERE status = 'delivered' AND delivery_date IS NOT NULL
        """
    )
    row = cur.fetchone()
    within, outside = row["within_30"], row["outside_30"]
    assert within > 0, "no delivered orders within 30 days"
    assert outside > 0, "no delivered orders outside 30 days"
    print(f"  delivered ≤30d  : {within}  |  >30d: {outside}")


def test_heavy_customer(cur: sqlite3.Cursor) -> None:
    cur.execute(
        "SELECT customer_id, COUNT(*) as n FROM orders GROUP BY customer_id ORDER BY n DESC LIMIT 1"
    )
    row = cur.fetchone()
    assert row["n"] >= 5, f"no customer with 5+ orders; max is {row['n']}"
    print(f"  top customer    : {row['customer_id']} — {row['n']} orders")


def test_out_of_stock_products(cur: sqlite3.Cursor) -> None:
    cur.execute("SELECT COUNT(*) FROM products WHERE stock = 0")
    n = cur.fetchone()[0]
    assert n >= 3, f"expected ≥3 products with stock=0, got {n}"
    print(f"  stock=0 products: {n}")


def test_check_constraints(cur: sqlite3.Cursor) -> None:
    """Verify CHECK constraints are enforced."""
    try:
        cur.execute(
            "INSERT INTO customers (name, email, phone, tier, created_at) VALUES ('Test','t@t.com','1234567890','diamond','2024-01-01')"
        )
        raise AssertionError("CHECK constraint on tier should have rejected 'diamond'")
    except sqlite3.IntegrityError:
        pass  # expected

    try:
        cur.execute(
            "INSERT INTO orders (customer_id, product_id, quantity, total, status, order_date, delivery_date) VALUES (1,1,0,100.0,'delivered','2024-01-01',NULL)"
        )
        raise AssertionError("CHECK constraint on quantity should have rejected 0")
    except sqlite3.IntegrityError:
        pass  # expected
    print("  CHECK constraints: enforced correctly")


def test_foreign_keys(cur: sqlite3.Cursor) -> None:
    """Orders reference valid customers and products."""
    cur.execute(
        """
        SELECT COUNT(*) FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.id
        WHERE c.id IS NULL
        """
    )
    orphan_orders = cur.fetchone()[0]
    assert orphan_orders == 0, f"{orphan_orders} orders reference non-existent customers"

    cur.execute(
        """
        SELECT COUNT(*) FROM refunds r
        LEFT JOIN orders o ON r.order_id = o.id
        WHERE o.id IS NULL
        """
    )
    orphan_refunds = cur.fetchone()[0]
    assert orphan_refunds == 0, f"{orphan_refunds} refunds reference non-existent orders"
    print("  foreign keys    : all valid")


# ── Phase 2: tool unit tests (no LLM) ────────────────────────────────────────

def test_lookup_order_valid() -> None:
    # Order 1 belongs to customer 1 (guaranteed by seed: first 6 orders go to customer 1)
    result = lookup_order.invoke({"order_id": 1, "customer_id": 1})
    assert "Order #1" in result, f"Expected order data, got: {result}"
    print(f"  result snippet  : {result.splitlines()[0]}")


def test_lookup_order_invalid() -> None:
    result = lookup_order.invoke({"order_id": 9999, "customer_id": 1})
    assert "No order found with ID 9999" in result, f"Expected not-found message, got: {result}"
    print(f"  result          : {result}")


def test_lookup_customer_orders_valid() -> None:
    result = lookup_customer_orders.invoke({"customer_id": 1})
    assert "Orders for customer 1" in result, f"Expected order list, got: {result}"
    print(f"  result snippet  : {result.splitlines()[0]}")


def test_check_refund_eligible() -> None:
    # Order 28 belongs to customer 11; delivered 2026-04-10, within 30-day window
    result = check_refund_eligibility.invoke({"order_id": 28, "customer_id": 11})
    assert "eligible" in result.lower(), f"Expected eligible, got: {result}"
    assert "not eligible" not in result.lower(), f"Should be eligible, got: {result}"
    print(f"  result          : {result}")


def test_check_refund_not_eligible() -> None:
    # Order 5 belongs to customer 1; status='processing' — cannot be refunded
    result = check_refund_eligibility.invoke({"order_id": 5, "customer_id": 1})
    assert "not eligible" in result.lower(), f"Expected not eligible, got: {result}"
    print(f"  result          : {result}")


def test_create_ticket() -> None:
    result = create_ticket.invoke({
        "customer_id": 1,
        "description": "My package arrived damaged.",
        "category": "complaint",
        "priority": "high",
        "order_id": 1,
    })
    assert "Ticket #" in result, f"Expected ticket confirmation, got: {result}"
    assert "created successfully" in result, f"Expected success message, got: {result}"
    print(f"  result snippet  : {result.splitlines()[0]}")


def test_search_knowledge_base_return_policy() -> None:
    result = search_knowledge_base.invoke({"question": "What is your return policy?"})
    assert "30 days" in result, f"Expected 30-day return info, got: {result}"
    print(f"  result snippet  : {result[:80]}…")


def test_search_knowledge_base_no_match() -> None:
    result = search_knowledge_base.invoke({"question": "Do you sell cryptocurrencies?"})
    assert "don't have information" in result.lower() or "contact" in result.lower(), (
        f"Expected fallback message, got: {result}"
    )
    print(f"  result          : {result}")


# ── runner ────────────────────────────────────────────────────────────────────

def main() -> None:
    # Always start from a clean, known-good DB
    print("Seeding database…")
    run_seed()

    print("=" * 55)
    print("Phase 1 Tests")
    print("=" * 55)

    conn = get_conn()
    cur = conn.cursor()
    # Enable FK enforcement for constraint tests
    cur.execute("PRAGMA foreign_keys = ON")

    tests = [
        ("Row counts",           test_row_counts),
        ("Status distributions", test_status_distributions),
        ("High-value orders",    test_high_value_orders),
        ("Delivery timing",      test_delivery_timing),
        ("Heavy customer",       test_heavy_customer),
        ("Out-of-stock products",test_out_of_stock_products),
        ("CHECK constraints",    test_check_constraints),
        ("Foreign keys",         test_foreign_keys),
    ]

    passed = 0
    for name, fn in tests:
        print(f"\n[{name}]")
        try:
            fn(cur)
            print(f"  PASS")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {e}")
        except Exception as e:
            print(f"  ERROR: {e}")

    conn.close()
    print(f"\n{'='*55}")
    print(f"Results: {passed}/{len(tests)} passed")
    print("=" * 55)

    # ── Phase 2: tool unit tests ──────────────────────────────────────────────
    print("\n" + "=" * 55)
    print("Phase 2 Tool Tests")
    print("=" * 55)

    p2_tests = [
        ("lookup_order (valid)",          test_lookup_order_valid),
        ("lookup_order (invalid)",        test_lookup_order_invalid),
        ("lookup_customer_orders",        test_lookup_customer_orders_valid),
        ("check_refund_eligibility (yes)",test_check_refund_eligible),
        ("check_refund_eligibility (no)", test_check_refund_not_eligible),
        ("create_ticket",                 test_create_ticket),
        ("search_knowledge_base (match)", test_search_knowledge_base_return_policy),
        ("search_knowledge_base (miss)",  test_search_knowledge_base_no_match),
    ]

    p2_passed = 0
    for name, fn in p2_tests:
        print(f"\n[{name}]")
        try:
            fn()
            print("  PASS")
            p2_passed += 1
        except AssertionError as e:
            print(f"  FAIL: {e}")
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\n{'='*55}")
    print(f"Results: {p2_passed}/{len(p2_tests)} passed")
    print("=" * 55)

    if passed < len(tests) or p2_passed < len(p2_tests):
        sys.exit(1)


if __name__ == "__main__":
    main()
