"""FAQ / knowledge base search tool."""

from langchain_core.tools import tool

# Keyed by a tuple of keywords; value is the answer
_FAQ: dict[tuple, str] = {
    ("return", "refund", "returns", "money back"): (
        "Our return policy allows returns within 30 days of delivery. "
        "Items must be unused and in original packaging. "
        "Initiate a return through your order page or contact support."
    ),
    ("shipping", "delivery time", "how long", "arrive", "dispatch"): (
        "Standard shipping takes 3-7 business days. "
        "Express shipping (1-2 days) is available at checkout for an additional fee. "
        "You will receive a tracking link once your order is dispatched."
    ),
    ("payment", "pay", "methods", "upi", "credit card", "debit card", "net banking"): (
        "We accept: Credit/Debit cards (Visa, Mastercard, RuPay), UPI (GPay, PhonePe, Paytm), "
        "Net Banking, EMI options, and Cash on Delivery (orders under ₹5,000)."
    ),
    ("cancel", "cancellation", "cancel order"): (
        "Orders can be cancelled only while in 'processing' status. "
        "Once shipped, cancellation is not possible — you may initiate a return after delivery. "
        "To cancel, go to My Orders and click 'Cancel Order'."
    ),
    ("contact", "support", "help", "reach", "phone", "email", "chat"): (
        "Reach our support team at:\n"
        "  Email : support@store.com\n"
        "  Phone : 1800-123-4567 (Mon–Sat, 9 AM–6 PM)\n"
        "  Chat  : available on our website and app."
    ),
    ("track", "tracking", "where is", "order status", "location"): (
        "Track your order using the order ID on our website under 'My Orders', "
        "or use the tracking link sent to your registered email/SMS after dispatch."
    ),
    ("warranty", "guarantee", "repair", "defective", "broken"): (
        "Electronics carry a 1-year manufacturer warranty. "
        "Other products carry a 6-month warranty. "
        "For warranty claims, contact support with your order ID and a photo of the defect."
    ),
    ("delete account", "close account", "remove account"): (
        "To delete your account, please contact support at support@store.com. "
        "Note: account deletion is permanent and all order history will be removed."
    ),
    ("exchange", "swap", "wrong size", "wrong colour", "wrong color"): (
        "Exchanges are available within 30 days of delivery for incorrect size or colour. "
        "Visit My Orders, select the item, and choose 'Exchange'. "
        "Exchanges are subject to stock availability."
    ),
    ("cod", "cash on delivery", "pay on delivery"): (
        "Cash on Delivery is available for orders under ₹5,000 in eligible pin codes. "
        "Select 'Cash on Delivery' at checkout to see if it is available for your address."
    ),
}


@tool
def search_knowledge_base(question: str) -> str:
    """Search the store FAQ for answers to common customer questions."""
    q = question.lower()
    for keywords, answer in _FAQ.items():
        if any(kw in q for kw in keywords):
            return answer
    return (
        "I don't have information about that. "
        "Please contact our support team at support@store.com or call 1800-123-4567."
    )
