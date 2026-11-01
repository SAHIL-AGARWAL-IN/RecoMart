"""Store business rules shared by views, checkout and seed data."""
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db.models import Case, F, FloatField, IntegerField, Q, Sum, Value, When
from django.db.models.functions import Cast, Coalesce
from django.utils import timezone

from .models import Interaction, Product

FREE_SHIPPING_THRESHOLD = Decimal("499")
SHIPPING_FEE = Decimal("49")
RECENTLY_VIEWED_KEY = "recently_viewed"
RECENTLY_VIEWED_MAX = 12

SORT_OPTIONS = {
    "popular": ("Most popular", ["-rating_count", "-rating_avg"]),
    "rating": ("Highest rated", ["-rating_avg", "-rating_count"]),
    "price_asc": ("Price: low to high", ["final_price"]),
    "price_desc": ("Price: high to low", ["-final_price"]),
    "newest": ("Newest first", ["-created_at"]),
    "discount": ("Biggest discount", ["price_ratio"]),
}
DEFAULT_SORT = "popular"


def shipping_fee_for(subtotal):
    """Orders of ₹499 or more ship free; smaller orders pay a flat ₹49."""
    return Decimal("0") if subtotal >= FREE_SHIPPING_THRESHOLD else SHIPPING_FEE


# ---------------------------------------------------------------- interactions
def ensure_session_key(request):
    """Guests need a session key so we can remember their cart and views."""
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key


def log_interaction(request, product, kind, quantity=1):
    """Record one shopper action. These rows are the recommender's training data."""
    user = request.user if request.user.is_authenticated else None
    return Interaction.objects.create(user=user, session_key=ensure_session_key(request), product=product,
                                      interaction_type=kind, quantity=quantity)


def remember_viewed(request, product):
    """Keep the last few viewed product ids in the session (works for guests too)."""
    viewed = [pid for pid in request.session.get(RECENTLY_VIEWED_KEY, []) if pid != product.id]
    request.session[RECENTLY_VIEWED_KEY] = [product.id, *viewed][:RECENTLY_VIEWED_MAX]


def recently_viewed(request, exclude=None, limit=8):
    ids = [pid for pid in request.session.get(RECENTLY_VIEWED_KEY, []) if pid != exclude][:limit]
    products = Product.objects.filter(id__in=ids, is_active=True).select_related("category")
    by_id = {p.id: p for p in products}
    return [by_id[pid] for pid in ids if pid in by_id]  # keep most-recent-first order


# -------------------------------------------------------------------- catalog
def with_prices(queryset):
    """Annotate the price the customer pays and the price ratio (for 'biggest discount')."""
    final = Coalesce("discount_price", "price")
    # Cast to float first: SQLite would otherwise do integer division (6299 / 10999 = 0).
    ratio = Cast(final, FloatField()) / Cast(F("price"), FloatField())
    return queryset.annotate(final_price=final, price_ratio=ratio)


def trending_products(limit=8, days=30):
    """Products with the most (weighted) shopper activity in the last `days` days."""
    since = timezone.now() - timedelta(days=days)
    weights = settings.INTERACTION_WEIGHTS
    score = Sum(
        Case(*[When(interactions__interaction_type=kind, then=Value(w)) for kind, w in weights.items()],
             default=Value(0), output_field=IntegerField()),
        filter=Q(interactions__timestamp__gte=since),
    )
    return (Product.objects.filter(is_active=True, stock__gt=0)
            .select_related("category")
            .annotate(trend_score=score)
            .filter(trend_score__gt=0)
            .order_by("-trend_score", "-rating_avg")[:limit])


def deal_products(limit=8):
    """In-stock products with the biggest percentage discount."""
    return (with_prices(Product.objects.filter(is_active=True, stock__gt=0, discount_price__isnull=False))
            .select_related("category")
            .order_by("price_ratio", "-rating_avg")[:limit])


def _decimal_or_none(value):
    try:
        number = Decimal(value)
        return number if number >= 0 else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def parse_filters(params, category=None):
    """Read and clean the filter values from request.GET."""
    sort = params.get("sort", DEFAULT_SORT)
    try:
        min_rating = int(params.get("rating", ""))
    except ValueError:
        min_rating = None
    return {
        "q": params.get("q", "").strip()[:100],
        "category": category.slug if category else params.get("category", ""),
        "min_price": _decimal_or_none(params.get("min_price")),
        "max_price": _decimal_or_none(params.get("max_price")),
        "rating": min_rating if min_rating in (1, 2, 3, 4) else None,
        "sort": sort if sort in SORT_OPTIONS else DEFAULT_SORT,
    }


def filter_products(filters):
    """Apply search, category, price, rating and sort filters with the Django ORM."""
    products = with_prices(Product.objects.filter(is_active=True)).select_related("category")
    if filters["q"]:
        q = filters["q"]
        products = products.filter(Q(name__icontains=q) | Q(brand__icontains=q) | Q(category__name__icontains=q)
                                   | Q(description__icontains=q))
    if filters["category"]:
        products = products.filter(category__slug=filters["category"])
    if filters["min_price"] is not None:
        products = products.filter(final_price__gte=filters["min_price"])
    if filters["max_price"] is not None:
        products = products.filter(final_price__lte=filters["max_price"])
    if filters["rating"]:
        products = products.filter(rating_avg__gte=filters["rating"])
    return products.order_by(*SORT_OPTIONS[filters["sort"]][1], "id")
