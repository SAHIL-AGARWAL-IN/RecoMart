from .cart import cart_count
from .models import Category


def store_nav(request):
    """Data every page needs for the navbar and footer."""
    user = getattr(request, "user", None)
    logged_in = bool(user and user.is_authenticated)
    return {
        "nav_categories": Category.objects.all(),
        "cart_count": cart_count(request),
        "wishlist_count": user.wishlist_items.count() if logged_in else 0,
    }
