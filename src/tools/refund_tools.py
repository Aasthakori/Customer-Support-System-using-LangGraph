"""Refund eligibility check and processing tools."""

from datetime import datetime

from langchain_core.tools import tool

from src.config import REFUND_WINDOW_DAYS, get_db_connection

VALID_REASONS = ("damaged", "wrong_item", "not_delivered", "quality_issue", "changed_mind")


def _get_order(order_id: int, customer_id: int):
    """Fetch the order row; returns None if not found or doesn't belong to customer_id."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM orders WHERE id = ? AND customer_id = ?",
            (order_id, customer_id),
        )
        return cur.fetchone()
    finally:
        conn.close()


def _eligibility_check(order_id: int, customer_id: int) -> tuple[bool, str]:
    """
    Core eligibility logic shared by both tools.
    Returns (eligible: bool, message: str).
    """
    row = _get_order(order_id, customer_id)

    if row is None:
        return False, f"Order {order_id} not found."

    if row["status"] != "delivered":
        return False, (
            f"Order {order_id} is not eligible for a refund. "
            f"Status is '{row['status']}'; only delivered orders can be refunded."
        )

    if not row["delivery_date"]:
        return False, f"Order {order_id} has no delivery date recorded."

    delivered_on = datetime.fromisoformat(row["delivery_date"])
    days_since = (datetime.now() - delivered_on).days

    if days_since > REFUND_WINDOW_DAYS:
        return False, (
            f"Order {order_id} is not eligible for a refund. "
            f"Delivered {days_since} days ago — refund window is {REFUND_WINDOW_DAYS} days."
        )

    return True, (
        f"Order {order_id} is eligible for a refund. "
        f"Delivered {days_since} day(s) ago. Total: ₹{row['total']:.2f}."
    )


@tool
def check_refund_eligibility(order_id: int, customer_id: int) -> str:
    """Check whether an order qualifies for a refund. Only checks orders belonging to customer_id."""
    if order_id <= 0 or customer_id <= 0:
        return "Invalid ID: order_id and customer_id must be positive integers."
    _, message = _eligibility_check(order_id, customer_id)
    return message


@tool
def process_refund(order_id: int, reason: str, customer_id: int) -> str:
    """
    Process a refund for a delivered order if it is within the refund window.
    Only processes orders belonging to customer_id.
    reason must be one of: damaged, wrong_item, not_delivered, quality_issue, changed_mind.
    """
    if reason not in VALID_REASONS:
        return (
            f"Invalid reason '{reason}'. "
            f"Must be one of: {', '.join(VALID_REASONS)}."
        )

    eligible, message = _eligibility_check(order_id, customer_id)
    if not eligible:
        return message

    row = _get_order(order_id, customer_id)
    amount = row["total"]
    now = datetime.now().isoformat(sep="T", timespec="seconds")

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE orders SET status = 'returned' WHERE id = ? AND customer_id = ?",
            (order_id, customer_id),
        )
        if cur.rowcount == 0:
            return (
                f"Error: order {order_id} could not be updated — "
                "it may not belong to this customer or no longer exists."
            )
        cur.execute(
            """
            INSERT INTO refunds (order_id, amount, reason, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
            """,
            (order_id, amount, reason, now),
        )
        conn.commit()
        refund_id = cur.lastrowid
    finally:
        conn.close()

    return (
        f"Refund initiated for order {order_id}.\n"
        f"  Refund ID : {refund_id}\n"
        f"  Amount    : ₹{amount:.2f}\n"
        f"  Reason    : {reason}\n"
        f"  Status    : pending (will be processed within 5-7 business days)"
    )
