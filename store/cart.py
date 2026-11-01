"""Cart service: everything the cart can do, kept out of the views.

Logged-in users own one cart (Cart.user). Guests' carts are found through the cart id
stored in their session. Django gives the session a new key at login but keeps its data,
so the cart id survives login and the guest cart can be merged into the user's cart.
"""
from decimal import Decimal

from django.db import transaction

from .models import Cart, CartItem
from .services import FREE_SHIPPING_THRESHOLD, ensure_session_key, shipping_fee_for

CART_SESSION_KEY = "cart_id"


class CartError(Exception):
    """A cart action that cannot be done, with a message the shopper can read."""


# ------------------------------------------------------------------- finding
def get_cart(request):
    """The current shopper's cart, or None if they don't have one yet."""
    if request.user.is_authenticated:
        return Cart.objects.filter(user=request.user).first()
    cart_id = request.session.get(CART_SESSION_KEY)
    return Cart.objects.filter(pk=cart_id, user__isnull=True).first() if cart_id else None


def get_or_create_cart(request):
    cart = get_cart(request)
    if cart:
        return cart
    if request.user.is_authenticated:
        return Cart.objects.create(user=request.user)
    cart = Cart.objects.create(session_key=ensure_session_key(request))
    request.session[CART_SESSION_KEY] = cart.id
    return cart


# ------------------------------------------------------------------- changing
def _check_available(product):
    if not product.is_active:
        raise CartError("This product is no longer available.")
    if product.stock <= 0:
        raise CartError(f"{product.name} is out of stock.")


def add_item(cart, product, quantity=1):
    """Add `quantity` of a product. Returns (item, capped) where capped means stock ran out."""
    _check_available(product)
    item, _ = CartItem.objects.get_or_create(cart=cart, product=product, defaults={"quantity": 0})
    wanted = item.quantity + max(1, int(quantity))
    item.quantity = min(wanted, product.stock)
    item.save()
    return item, wanted > product.stock


def set_quantity(cart, product_id, quantity):
    """Set an exact quantity (0 removes the item). Returns (item or None, capped)."""
    item = cart.items.select_related("product").filter(product_id=product_id).first()
    if item is None:
        raise CartError("That product is not in your cart.")
    quantity = int(quantity)
    if quantity <= 0:
        item.delete()
        return None, False
    _check_available(item.product)
    item.quantity = min(quantity, item.product.stock)
    item.save()
    return item, quantity > item.product.stock


def remove_item(cart, product_id):
    cart.items.filter(product_id=product_id).delete()


@transaction.atomic
def merge_carts(source, target):
    """Move every item from `source` (a guest cart) into `target`, then delete `source`."""
    for item in source.items.select_related("product"):
        existing = target.items.filter(product=item.product).first()
        total = item.quantity + (existing.quantity if existing else 0)
        CartItem.objects.update_or_create(cart=target, product=item.product,
                                          defaults={"quantity": min(total, item.product.stock)})
    source.delete()


def merge_session_cart_on_login(request, user):
    """Called by the user_logged_in signal (see accounts/signals.py)."""
    cart_id = request.session.pop(CART_SESSION_KEY, None)
    guest_cart = Cart.objects.filter(pk=cart_id, user__isnull=True).first() if cart_id else None
    if guest_cart is None:
        return
    user_cart, _ = Cart.objects.get_or_create(user=user)
    merge_carts(guest_cart, user_cart)


# ------------------------------------------------------------------- reading
def summary(cart):
    """Totals for the cart page, the checkout sidebar and the navbar badge."""
    items = list(cart.items.select_related("product")) if cart else []
    subtotal = sum((item.line_total for item in items), Decimal("0"))
    shipping = shipping_fee_for(subtotal) if items else Decimal("0")
    return {
        "items": items,
        "count": sum(item.quantity for item in items),
        "subtotal": subtotal,
        "shipping": shipping,
        "total": subtotal + shipping,
        "free_shipping_remaining": max(Decimal("0"), FREE_SHIPPING_THRESHOLD - subtotal),
        "free_shipping_progress": min(100, int(subtotal * 100 / FREE_SHIPPING_THRESHOLD)),
    }


def cart_count(request):
    """Total quantity of items, for the navbar badge."""
    cart = get_cart(request)
    return cart.total_quantity if cart else 0
