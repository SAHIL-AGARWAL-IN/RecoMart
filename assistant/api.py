"""POST /api/assistant/ : the chat endpoint. JSON in, JSON out, CSRF-protected like every POST."""
import json

from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from store.models import Category, Product
from store.services import ensure_session_key
from store.templatetags.store_tags import inr

from . import intents, responder

MAX_MESSAGE_LENGTH = 500
RATE_LIMIT = 20          # messages ...
RATE_WINDOW_SECONDS = 60  # ... per minute, per visitor


def _too_many(request):
    """A simple per-session counter in the cache. Stops scripts from hammering the endpoint."""
    key = f"assistant:rate:{ensure_session_key(request)}"
    count = cache.get_or_set(key, 0, RATE_WINDOW_SECONDS)
    if count >= RATE_LIMIT:
        return True
    try:
        cache.incr(key)
    except ValueError:  # the key expired between the two calls
        cache.set(key, 1, RATE_WINDOW_SECONDS)
    return False


def _card(product, wishlist_ids):
    return {
        "id": product.id, "name": product.name, "brand": product.brand, "url": product.get_absolute_url(),
        "image": product.image.url if product.image else "", "price": inr(product.effective_price),
        "mrp": inr(product.price) if product.discount_price else "", "rating": float(product.rating_avg),
        "rating_count": product.rating_count, "in_stock": product.in_stock,
        "wishlisted": product.id in wishlist_ids,
    }


@require_POST
def reply(request):
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        data = {}
    message = str(data.get("message", "")).strip()
    if not message or len(message) > MAX_MESSAGE_LENGTH:
        return JsonResponse({"error": f"Type a message of up to {MAX_MESSAGE_LENGTH} characters."}, status=400)
    if _too_many(request):
        return JsonResponse({"error": "You're sending messages very fast. Please wait a moment."}, status=429)

    # On a product page the panel sends that product's id, so "similar to this" works.
    current = None
    if str(data.get("product_id", "")).isdigit():
        current = Product.objects.filter(pk=int(data["product_id"]), is_active=True).first()

    intent = intents.classify(message, list(Category.objects.values_list("slug", flat=True)))
    handler = responder.HANDLERS[intent.name]
    answer = handler(message, request, current) if intent.name == "similar" else handler(message, request)

    wishlist_ids = set()
    if request.user.is_authenticated:
        wishlist_ids = set(request.user.wishlist_items.values_list("product_id", flat=True))
    return JsonResponse({
        "intent": intent.name,
        "confidence": round(intent.confidence, 2),
        "text": answer["text"],
        "products": [_card(p, wishlist_ids) for p in answer["products"]],
        "chips": answer["chips"],
        "link": answer["link"],
    })
