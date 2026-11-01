"""JSON API for recommendations, called with fetch() by static/js/recommendations.js."""
from urllib.parse import urlencode

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from store.models import Product
from store.templatetags.store_tags import inr

from . import services
from .models import RecommendationEvent

SIMILAR = RecommendationEvent.Widget.SIMILAR


def _card(suggestion, widget, source_product, wishlist_ids):
    """Everything the JavaScript needs to draw one recommendation card."""
    product = suggestion.product
    tracking = urlencode({"rec": widget, "src": source_product.id})  # lets the product page log the click
    return {
        "id": product.id,
        "name": product.name,
        "brand": product.brand,
        "url": f"{product.get_absolute_url()}?{tracking}",
        "image": product.image.url if product.image else "",
        "price": inr(product.effective_price),
        "mrp": inr(product.price) if product.discount_price else "",
        "discount_percent": product.discount_percent,
        "rating": float(product.rating_avg),
        "rating_count": product.rating_count,
        "in_stock": product.in_stock,
        "wishlisted": product.id in wishlist_ids,
        "score": suggestion.score,
    }


@require_GET
def similar(request, product_id):
    """GET /api/recommendations/<product_id>/ : "You may also like" for one product."""
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    suggestions = services.similar_products(product)
    services.log_impressions(request, [s.product for s in suggestions], SIMILAR, source_product=product)

    wishlist_ids = set()
    if request.user.is_authenticated:
        wishlist_ids = set(request.user.wishlist_items.values_list("product_id", flat=True))
    return JsonResponse({
        "product_id": product.id,
        "widget": SIMILAR,
        "model_version": services.model_version(),
        "source": suggestions[0].source if suggestions else None,
        "results": [_card(s, SIMILAR, product, wishlist_ids) for s in suggestions],
    })
