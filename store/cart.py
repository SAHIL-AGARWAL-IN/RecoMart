"""Cart service: find the shopper's cart. Phase 3 adds add / update / remove / merge."""
from .models import Cart


def get_cart(request):
    """The cart of the logged-in user, or of this guest's session. None if there isn't one yet."""
    if request.user.is_authenticated:
        return Cart.objects.filter(user=request.user).first()
    if request.session.session_key:
        return Cart.objects.filter(user__isnull=True, session_key=request.session.session_key).first()
    return None


def cart_count(request):
    """Total quantity of items, for the navbar badge."""
    cart = get_cart(request)
    return cart.total_quantity if cart else 0
