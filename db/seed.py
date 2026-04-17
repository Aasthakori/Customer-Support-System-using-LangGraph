"""Seed the SQLite database with realistic Indian e-commerce data using Faker."""

import os
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker

random.seed(42)
fake = Faker("en_IN")
Faker.seed(42)

DB_PATH = Path(__file__).parent / "customer_support.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


# ── helpers ──────────────────────────────────────────────────────────────────

def iso(dt: datetime) -> str:
    return dt.isoformat(sep="T", timespec="seconds")


def days_ago(n: int) -> datetime:
    return datetime.now() - timedelta(days=n)


# ── data pools ───────────────────────────────────────────────────────────────

TIERS = ["bronze", "silver", "gold", "platinum"]
CATEGORIES = ["electronics", "clothing", "home", "books", "sports", "beauty", "toys", "food"]
ORDER_STATUSES = ["pending", "processing", "shipped", "delivered", "cancelled", "returned"]
TICKET_CATEGORIES = ["complaint", "technical", "billing", "general"]
PRIORITIES = ["low", "medium", "high"]
TICKET_STATUSES = ["open", "in_progress", "resolved", "closed"]
REFUND_REASONS = ["damaged", "wrong_item", "not_delivered", "quality_issue", "changed_mind"]
REFUND_STATUSES = ["pending", "approved", "rejected", "processed"]


PRODUCT_TEMPLATES = [
    ("Samsung Galaxy S23", "electronics", 49999),
    ("Apple AirPods Pro", "electronics", 24999),
    ("Sony WH-1000XM5 Headphones", "electronics", 29999),
    ("Lenovo IdeaPad Laptop", "electronics", 54999),
    ("Boat Rockerz 450 BT", "electronics", 1499),
    ("Realme Buds Air 3", "electronics", 3499),
    ("Philips Air Fryer", "home", 6999),
    ("Prestige Pressure Cooker", "home", 1299),
    ("Milton Thermosteel Flask", "home", 849),
    ("Asian Paints Royale Shyne", "home", 2199),
    ("Usha Tower Fan", "home", 4499),
    ("Bajaj Mixer Grinder", "home", 2699),
    ("Allen Solly Formal Shirt", "clothing", 1299),
    ("Levis 511 Slim Jeans", "clothing", 2999),
    ("Puma Running Shoes", "sports", 3499),
    ("Nike Air Max 270", "sports", 8999),
    ("Adidas Track Pants", "clothing", 1799),
    ("Wildcraft Backpack 45L", "sports", 2499),
    ("Cosco Football", "sports", 699),
    ("Yoga Mat 6mm", "sports", 599),
    ("Atomic Habits", "books", 349),
    ("Rich Dad Poor Dad", "books", 299),
    ("The Psychology of Money", "books", 399),
    ("Zero to One", "books", 449),
    ("Deep Work", "books", 379),
    ("Lakme Face Serum", "beauty", 549),
    ("Mamaearth Vitamin C Cream", "beauty", 349),
    ("WOW Shampoo 300ml", "beauty", 399),
    ("Biotique Bio Honey Gel", "beauty", 199),
    ("Forest Essentials Face Oil", "beauty", 1995),
    ("Funskool Ludo Star", "toys", 399),
    ("LEGO Classic Set", "toys", 2999),
    ("Hot Wheels 10-Car Pack", "toys", 899),
    ("Nerf Elite 2.0", "toys", 1499),
    ("Hasbro Monopoly", "toys", 999),
    ("Haldirams Assorted Namkeen 1kg", "food", 349),
    ("Tata Tea Gold 500g", "food", 299),
    ("Bagrry's Corn Flakes 1kg", "food", 449),
    ("Saffola Gold Oil 5L", "food", 899),
    ("MTR Masala Dosa Mix 500g", "food", 199),
    ("OnePlus Nord CE 3", "electronics", 26999),
    ("JBL Flip 6 Speaker", "electronics", 11999),
    ("Xiaomi Smart TV 43\"", "electronics", 29999),
    ("Bosch Washing Machine 7kg", "home", 34999),
    ("Whirlpool Refrigerator 340L", "home", 39999),
    ("Crompton Ceiling Fan", "home", 2499),
    ("FabIndia Kurta Set", "clothing", 2499),
    ("W Floral Dress", "clothing", 1799),
    ("Biba Ethnic Top", "clothing", 999),
    ("Manyavar Sherwani", "clothing", 8999),
]


# ── seed functions ────────────────────────────────────────────────────────────

def seed_customers(cur: sqlite3.Cursor) -> list[int]:
    customer_ids = []
    for i in range(20):
        tier = random.choices(TIERS, weights=[50, 30, 15, 5])[0]
        created = iso(days_ago(random.randint(30, 730)))
        cur.execute(
            "INSERT INTO customers (name, email, phone, tier, created_at) VALUES (?,?,?,?,?)",
            (fake.name(), fake.unique.email(), fake.phone_number()[:15], tier, created),
        )
        customer_ids.append(cur.lastrowid)
    return customer_ids


def seed_products(cur: sqlite3.Cursor) -> list[int]:
    product_ids = []
    for i, (name, cat, base_price) in enumerate(PRODUCT_TEMPLATES):
        price = round(base_price * random.uniform(0.9, 1.1), 2)
        # guarantee at least 3 products with stock=0
        if i < 3:
            stock = 0
        else:
            stock = random.randint(0, 200)
        cur.execute(
            "INSERT INTO products (name, category, price, stock, description) VALUES (?,?,?,?,?)",
            (name, cat, price, stock, fake.sentence(nb_words=12)),
        )
        product_ids.append(cur.lastrowid)
    return product_ids


def seed_orders(cur: sqlite3.Cursor, customer_ids: list[int], product_ids: list[int]) -> list[int]:
    order_ids = []

    # Guarantee one customer with 5+ orders (customer index 0)
    heavy_customer = customer_ids[0]
    heavy_count = 0

    for i in range(80):
        # First 6 orders go to the heavy customer
        if heavy_count < 6:
            cid = heavy_customer
            heavy_count += 1
        else:
            cid = random.choice(customer_ids)

        pid = random.choice(product_ids)
        qty = random.randint(1, 5)

        # Fetch price from already-inserted product
        cur.execute("SELECT price FROM products WHERE id=?", (pid,))
        price = cur.fetchone()[0]
        total = round(price * qty, 2)

        # Guarantee some orders with total > 5000
        if i < 10:
            # Force high-value order by picking an electronics product
            cur.execute(
                "SELECT id, price FROM products WHERE category='electronics' ORDER BY RANDOM() LIMIT 1"
            )
            row = cur.fetchone()
            if row:
                pid, price = row
                qty = random.randint(1, 3)
                total = round(price * qty, 2)

        status = random.choices(
            ORDER_STATUSES, weights=[5, 10, 15, 50, 10, 10]
        )[0]

        order_date_dt = days_ago(random.randint(1, 120))
        order_date = iso(order_date_dt)

        # delivered within 30 days (some), outside 30 days (some)
        if status == "delivered":
            if i % 3 == 0:
                # delivered OUTSIDE 30 days
                delivery_days = random.randint(31, 60)
            else:
                # delivered within 30 days
                delivery_days = random.randint(2, 29)
            delivery_date = iso(order_date_dt + timedelta(days=delivery_days))
        else:
            delivery_date = None

        cur.execute(
            "INSERT INTO orders (customer_id, product_id, quantity, total, status, order_date, delivery_date) VALUES (?,?,?,?,?,?,?)",
            (cid, pid, qty, total, status, order_date, delivery_date),
        )
        order_ids.append(cur.lastrowid)

    return order_ids


def seed_tickets(
    cur: sqlite3.Cursor, customer_ids: list[int], order_ids: list[int]
) -> list[int]:
    ticket_ids = []
    for _ in range(15):
        cur.execute(
            "INSERT INTO tickets (customer_id, order_id, category, priority, status, description, created_at) VALUES (?,?,?,?,?,?,?)",
            (
                random.choice(customer_ids),
                random.choice(order_ids) if random.random() > 0.2 else None,
                random.choice(TICKET_CATEGORIES),
                random.choice(PRIORITIES),
                random.choice(TICKET_STATUSES),
                fake.sentence(nb_words=15),
                iso(days_ago(random.randint(1, 60))),
            ),
        )
        ticket_ids.append(cur.lastrowid)
    return ticket_ids


def seed_refunds(cur: sqlite3.Cursor, order_ids: list[int]) -> None:
    # pick 10 distinct orders for refunds
    refund_orders = random.sample(order_ids, 10)
    for oid in refund_orders:
        cur.execute("SELECT total FROM orders WHERE id=?", (oid,))
        total = cur.fetchone()[0]
        amount = round(min(total, total * random.uniform(0.5, 1.0)), 2)
        cur.execute(
            "INSERT INTO refunds (order_id, amount, reason, status, created_at) VALUES (?,?,?,?,?)",
            (
                oid,
                amount,
                random.choice(REFUND_REASONS),
                random.choice(REFUND_STATUSES),
                iso(days_ago(random.randint(1, 30))),
            ),
        )


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    # Remove existing DB so seed is idempotent.
    # Requires --force flag or interactive confirmation to prevent accidental data loss.
    if DB_PATH.exists():
        import sys
        if "--force" in sys.argv:
            DB_PATH.unlink()
        else:
            answer = input(f"Delete existing database at {DB_PATH}? [y/N]: ").strip().lower()
            if answer != "y":
                print("Aborted.")
                sys.exit(0)
            DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(SCHEMA_PATH.read_text())

    print("Seeding customers …", end=" ")
    customer_ids = seed_customers(cur)
    print(f"done ({len(customer_ids)})")

    print("Seeding products  …", end=" ")
    product_ids = seed_products(cur)
    print(f"done ({len(product_ids)})")

    print("Seeding orders    …", end=" ")
    order_ids = seed_orders(cur, customer_ids, product_ids)
    print(f"done ({len(order_ids)})")

    print("Seeding tickets   …", end=" ")
    seed_tickets(cur, customer_ids, order_ids)
    print("done (15)")

    print("Seeding refunds   …", end=" ")
    seed_refunds(cur, order_ids)
    print("done (10)")

    conn.commit()
    conn.close()
    print(f"\nDatabase written to: {DB_PATH}")


if __name__ == "__main__":
    main()
