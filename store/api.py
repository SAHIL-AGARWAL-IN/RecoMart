"""JSON endpoints called by the page's JavaScript with fetch().

Every POST is protected by Django's CSRF check; main.js sends the token in a header.
"""
import json
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db.models import Case, IntegerField, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from . import cart as cart_service
from . import services
from .models import Category, Interaction, Product, WishlistItem
from .templatetags.store_tags import inr

SEARCH_LIMIT = 6


def _payload(request):
    """Accept both JSON bodies (fetch) and normal form posts."""
    if request.content_type == "application/json":
        try:
            return json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return {}
    return request.POST


def _quantity(data, default=1):
    try:
        return int(data.get("quantity", default))
    except (TypeError, ValueError):
        return default


def _cart_json(cart):
    totals = cart_service.summary(cart)
    return {
        "count": totals["count"],
        "subtotal": inr(totals["subtotal"]),
        "shipping": "Free" if not totals["shipping"] else inr(totals["shipping"]),
        "total": inr(totals["total"]),
        "free_shipping_remaining": inr(totals["free_shipping_remaining"]),
        "free_shipping_progress": totals["free_shipping_progress"],
    }


def _item_json(item):
    if item is None:
        return None
    return {"product_id": item.product_id, "quantity": item.quantity, "line_total": inr(item.line_total),
            "max": item.product.stock}


# ------------------------------------------------------------------------ cart
@require_POST
def cart_add(request):
    data = _payload(request)
    product = get_object_or_404(Product, pk=data.get("product_id"))
    cart = cart_service.get_or_create_cart(request)
    try:
        item, capped = cart_service.add_item(cart, product, _quantity(data))
    except cart_service.CartError as error:
        return JsonResponse({"error": str(error)}, status=400)
    services.log_interaction(request, product, Interaction.Type.CART, quantity=_quantity(data))
    message = (f"Only {product.stock} in stock, so your cart has the maximum." if capped
               else f"Added {product.name} to your cart.")
    return JsonResponse({"message": message, "item": _item_json(item), "cart": _cart_json(cart)})


@require_POST
def cart_update(request):
    data = _payload(request)
    cart = cart_service.get_cart(request)
    if cart is None:
        return JsonResponse({"error": "Your cart is empty."}, status=400)
    try:
        item, capped = cart_service.set_quantity(cart, data.get("product_id"), _quantity(data))
    except cart_service.CartError as error:
        return JsonResponse({"error": str(error)}, status=400)
    message = f"Only {item.product.stock} in stock." if capped else ""
    return JsonResponse({"message": message, "item": _item_json(item), "cart": _cart_json(cart)})


@require_POST
def cart_remove(request):
    cart = cart_service.get_cart(request)
    if cart is not None:
        cart_service.remove_item(cart, _payload(request).get("product_id"))
    return JsonResponse({"message": "Removed from your cart.", "item": None, "cart": _cart_json(cart)})


# -------------------------------------------------------------------- wishlist
@require_POST
def wishlist_toggle(request, product_id):
    if not request.user.is_authenticated:
        next_url = request.headers.get("Referer", "/")
        login_url = f"{reverse('accounts:login')}?{urlencode({'next': next_url})}"
        return JsonResponse({"error": "Log in to save products to your wishlist.", "login_url": login_url},
                            status=401)
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    item = WishlistItem.objects.filter(user=request.user, product=product).first()
    if item:
        item.delete()
        wishlisted, message = False, "Removed from your wishlist."
    else:
        WishlistItem.objects.create(user=request.user, product=product)
        services.log_interaction(request, product, Interaction.Type.WISHLIST)
        wishlisted, message = True, "Saved to your wishlist."
    return JsonResponse({"wishlisted": wishlisted, "message": message,
                         "count": request.user.wishlist_items.count()})


# ---------------------------------------------------------------------- search
@require_GET
def search(request):
    """Live search dropdown: a few matching products as plain data."""
    query = request.GET.get("q", "").strip()
    if len(query) < 2:
        return JsonResponse({"query": query, "results": [], "total": 0})
    # Products whose name matches come first; brand/description-only matches after them.
    name_first = Case(When(name__icontains=query, then=Value(0)), default=Value(1), output_field=IntegerField())
    products = services.filter_products(services.parse_filters({"q": query})).order_by(
        name_first, "-rating_count", "id")
    results = [{
        "name": p.name,
        "brand": p.brand,
        "category": p.category.name,
        "price": inr(p.effective_price),
        "image": p.image.url if p.image else "",
        "url": p.get_absolute_url(),
    } for p in products[:SEARCH_LIMIT]]
    return JsonResponse({"query": query, "results": results, "total": products.count(),
                         "see_all_url": f"{reverse('store:product_list')}?{urlencode({'q': query})}"})


@require_GET
def products(request):
    """AJAX filters: the product grid, re-rendered on the server as HTML inside JSON."""
    category = None
    if request.GET.get("category"):
        category = Category.objects.filter(slug=request.GET["category"]).first()
    filters = services.parse_filters(request.GET, category=category)
    page = Paginator(services.filter_products(filters), services.PRODUCTS_PER_PAGE).get_page(request.GET.get("page"))
    html = render_to_string("store/_product_results.html", {"page": page, "filters": filters, "category": category},
                            request=request)
    return JsonResponse({"count": page.paginator.count, "page": page.number,
                         "has_next": page.has_next(), "html": html})
