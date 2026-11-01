"""JSON API for recommendations, called with fetch() by static/js/recommendations.js."""
from urllib.parse import urlencode

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from store import cart as cart_service
from store.models import Product
from store.templatetags.store_tags import inr

from . import services
from .models import RecommendationEvent

Widget = RecommendationEvent.Widget


def _card(suggestion, widget, source_product, wishlist_ids):
    """Everything the JavaScript needs to draw one recommendation card."""
    product = suggestion.product
    tracking = {"rec": widget}  # lets the product page log the click
    if source_product is not None:
        tracking["src"] = source_product.id
    return {
        "id": product.id,
        "name": product.name,
        "brand": product.brand,
        "url": f"{product.get_absolute_url()}?{urlencode(tracking)}",
        "image": product.image.url if product.image else "",
        "price": inr(product.effective_price),
        "mrp": inr(product.price) if product.discount_price else "",
        "discount_percent": product.discount_percent,
        "rating": float(product.rating_avg),
        "rating_count": product.rating_count,
        "in_stock": product.in_stock,
        "wishlisted": product.id in wishlist_ids,
        "score": suggestion.score,
        "reasons": suggestion.reasons,
    }


def _respond(request, suggestions, widget, source_product=None, **extra):
    """Log impressions and return the cards as JSON."""
    services.log_impressions(request, [s.product for s in suggestions], widget, source_product=source_product)
    wishlist_ids = set()
    if request.user.is_authenticated:
        wishlist_ids = set(request.user.wishlist_items.values_list("product_id", flat=True))
    return JsonResponse({
        "widget": widget,
        "model_version": services.model_version(),
        "results": [_card(s, widget, source_product, wishlist_ids) for s in suggestions],
        **extra,
    })


@require_GET
def similar(request, product_id):
    """GET /api/recommendations/<product_id>/ : "You may also like" for one product."""
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    suggestions = services.similar_products(product)
    return _respond(request, suggestions, Widget.SIMILAR, source_product=product, product_id=product.id,
                    source=suggestions[0].source if suggestions else None)


@require_GET
def for_you(request):
    """GET /api/recommendations/for-you/ : personal feed, or trending for guests and new shoppers."""
    mode, suggestions = services.recommended_for(request.user)
    if mode == "personal":
        subtitle = "Based on what you've viewed, saved and bought recently."
    else:
        subtitle = "Popular right now. Browse a few products and this becomes personal."
    widget = Widget.FOR_YOU if mode == "personal" else Widget.TRENDING
    return _respond(request, suggestions, widget, mode=mode, subtitle=subtitle)


@require_GET
def frequently_bought(request):
    """GET /api/recommendations/frequently-bought/ : based on what is in the shopper's cart."""
    cart = cart_service.get_cart(request)
    product_ids = list(cart.items.values_list("product_id", flat=True)) if cart else []
    suggestions = services.frequently_bought_together(product_ids)
    source = Product.objects.filter(pk=product_ids[0]).first() if product_ids else None
    return _respond(request, suggestions, Widget.FBT, source_product=source)
