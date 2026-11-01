"""Store business rules shared by views, checkout and seed data."""
from decimal import Decimal

FREE_SHIPPING_THRESHOLD = Decimal("499")
SHIPPING_FEE = Decimal("49")


def shipping_fee_for(subtotal):
    """Orders of ₹499 or more ship free; smaller orders pay a flat ₹49."""
    return Decimal("0") if subtotal >= FREE_SHIPPING_THRESHOLD else SHIPPING_FEE
