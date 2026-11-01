from .cart import cart_count
from .models import Category


def store_nav(request):
    """Data every page needs: navbar categories, badge counts and which products are wishlisted."""
    user = getattr(request, "user", None)
    wishlist_ids = set()
    if user and user.is_authenticated:
        wishlist_ids = set(user.wishlist_items.values_list("product_id", flat=True))
    return {
        "nav_categories": Category.objects.all(),
        "cart_count": cart_count(request),
        "wishlist_count": len(wishlist_ids),
        "wishlist_ids": wishlist_ids,
    }
