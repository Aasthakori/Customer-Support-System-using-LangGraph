"""Support ticket creation tool."""

import sqlite3
from datetime import datetime
from typing import Optional

from langchain_core.tools import tool

from src.config import get_db_connection

VALID_CATEGORIES = ("complaint", "technical", "billing", "general")
VALID_PRIORITIES = ("low", "medium", "high")


@tool
def create_ticket(
    customer_id: int,
    description: str,
    category: str,
    priority: str,
    order_id: Optional[int] = None,
) -> str:
    """
    Create a support ticket for a customer issue.
    customer_id must be the verified customer's ID.
    category must be one of: complaint, technical, billing, general.
    priority must be one of: low, medium, high.
    If order_id is provided, it must belong to customer_id.
    """
    if customer_id <= 0:
        return "Invalid ID: customer_id must be a positive integer."
    if order_id is not None and order_id <= 0:
        return "Invalid ID: order_id must be a positive integer."
    if not description.strip():
        return "Error: ticket description cannot be empty."
    if category not in VALID_CATEGORIES:
        return (
            f"Invalid category '{category}'. "
            f"Must be one of: {', '.join(VALID_CATEGORIES)}."
        )
    if priority not in VALID_PRIORITIES:
        return (
            f"Invalid priority '{priority}'. "
            f"Must be one of: {', '.join(VALID_PRIORITIES)}."
        )

    conn = get_db_connection()

    # If an order is referenced, verify it belongs to this customer.
    if order_id is not None:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM orders WHERE id = ? AND customer_id = ?",
                (order_id, customer_id),
            )
            if cur.fetchone() is None:
                conn.close()
                return f"No order found with ID {order_id}"
        except sqlite3.DatabaseError:
            conn.close()
            raise

    now = datetime.now().isoformat(sep="T", timespec="seconds")
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO tickets
                (customer_id, order_id, category, priority, status, description, created_at)
            VALUES (?, ?, ?, ?, 'open', ?, ?)
            """,
            (customer_id, order_id, category, priority, description, now),
        )
        conn.commit()
        ticket_id = cur.lastrowid
    finally:
        conn.close()

    return (
        f"Ticket #{ticket_id} created successfully.\n"
        f"  Customer  : {customer_id}\n"
        f"  Category  : {category}\n"
        f"  Priority  : {priority}\n"
        f"  Status    : open\n"
        f"  Order     : {order_id if order_id else 'N/A'}\n"
        f"  Description: {description}"
    )
