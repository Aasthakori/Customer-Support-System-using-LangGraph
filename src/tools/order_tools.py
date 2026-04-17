"""Order lookup tools for the order agent."""

from langchain_core.tools import tool

from src.config import get_db_connection


@tool
def lookup_order(order_id: int, customer_id: int) -> str:
    """Look up a single order by its ID. Only returns orders that belong to customer_id."""
    if order_id <= 0 or customer_id <= 0:
        return "Invalid ID: order_id and customer_id must be positive integers."
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT orders.id, orders.status, orders.quantity, orders.total,
                   orders.order_date, orders.delivery_date,
                   products.name  AS product_name,
                   customers.name AS customer_name
            FROM   orders
            JOIN   products  ON orders.product_id  = products.id
            JOIN   customers ON orders.customer_id = customers.id
            WHERE  orders.id = ?
            AND    orders.customer_id = ?
            """,
            (order_id, customer_id),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        return f"No order found with ID {order_id}"

    return (
        f"Order #{row['id']}\n"
        f"  Customer      : {row['customer_name']}\n"
        f"  Product       : {row['product_name']}\n"
        f"  Quantity      : {row['quantity']}\n"
        f"  Total         : ₹{row['total']:.2f}\n"
        f"  Status        : {row['status']}\n"
        f"  Order date    : {row['order_date']}\n"
        f"  Delivery date : {row['delivery_date'] or 'Not yet delivered'}"
    )


@tool
def lookup_customer_orders(customer_id: int) -> str:
    """Look up all orders placed by a customer, newest first."""
    if customer_id <= 0:
        return "Invalid ID: customer_id must be a positive integer."
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT orders.id, orders.status, orders.quantity, orders.total,
                   orders.order_date, orders.delivery_date,
                   products.name  AS product_name,
                   customers.name AS customer_name
            FROM   orders
            JOIN   products  ON orders.product_id  = products.id
            JOIN   customers ON orders.customer_id = customers.id
            WHERE  orders.customer_id = ?
            ORDER  BY orders.order_date DESC
            """,
            (customer_id,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return f"No orders found for customer {customer_id}"

    lines = [f"Orders for customer {customer_id} ({rows[0]['customer_name']}):"]
    for row in rows:
        lines.append(
            f"  Order #{row['id']} | {row['product_name']} | "
            f"qty {row['quantity']} | ₹{row['total']:.2f} | "
            f"status: {row['status']} | ordered: {row['order_date'][:10]}"
        )
    return "\n".join(lines)
