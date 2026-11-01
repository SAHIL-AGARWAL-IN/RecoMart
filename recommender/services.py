"""Database glue for the recommender: saving training results, serving recommendations, logging events.

The ML maths lives in engine.py; this file connects it to Django models.
"""
import hashlib
import math
from dataclasses import dataclass, field
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Case, Count, IntegerField, Sum, Value, When
from django.utils import timezone

from store.models import Interaction, OrderItem, Product
from store.services import ensure_session_key, trending_products

from . import engine, explain, features
from .models import RecommendationData, RecommendationEvent, RecommenderSettings, TrainingRun

WIDGETS = {choice.value for choice in RecommendationEvent.Widget}
VECTOR_DECIMALS = 5
POPULARITY_DAYS = 30
POPULARITY_CACHE_SECONDS = 300
PROFILE_SIZE = 20          # how many recent interactions build a shopper's taste profile
PROFILE_HALF_LIFE_DAYS = 30
PERSONAL_CANDIDATES = 40
SHOPPERS_LIKE_YOU_TOP = 3  # at most this many cards per strip get "Popular with shoppers like you"


@dataclass
class Suggestion:
    product: Product
    score: float | None          # cosine similarity (None when it doesn't come from the model)
    source: str                  # "model", "fallback", "personal", "trending" or "fbt"
    final: float = 0.0           # hybrid score used for ordering
    reasons: list = field(default_factory=list)  # "Why this?" chips
    together: int = 0            # times bought together (frequently-bought-together only)


# --------------------------------------------------------------- popularity and hybrid ranking
def popularity_scores():
    """{product_id: 0..1}: type-weighted shopper activity in the last 30 days, log-scaled.

    Cached for 5 minutes because every recommendation request needs it.
    """
    scores = cache.get("recommender:popularity")
    if scores is None:
        since = timezone.now() - timedelta(days=POPULARITY_DAYS)
        weight = Case(*[When(interaction_type=kind, then=Value(w)) for kind, w in settings.INTERACTION_WEIGHTS.items()],
                      default=Value(0), output_field=IntegerField())
        rows = (Interaction.objects.filter(timestamp__gte=since).values("product_id")
                .annotate(total=Sum(weight)))
        raw = {row["product_id"]: math.log1p(row["total"] or 0) for row in rows}
        top = max(raw.values(), default=0) or 1.0
        scores = {product_id: value / top for product_id, value in raw.items()}
        cache.set("recommender:popularity", scores, POPULARITY_CACHE_SECONDS)
    return scores


def _rank(suggestions, ranking="hybrid"):
    """Order suggestions: hybrid score (or pure similarity), with out-of-stock products last."""
    weights = settings.RECOMMENDER["HYBRID_WEIGHTS"]
    popularity = popularity_scores()
    now = timezone.now()
    for s in suggestions:
        similarity = s.score or 0.0
        if ranking == "similarity":
            s.final = similarity
        else:
            age_days = (now - s.product.created_at).days
            s.final = engine.hybrid_score(similarity, popularity.get(s.product.id, 0.0),
                                          engine.recency_score(age_days), weights)
    suggestions.sort(key=lambda s: (not s.product.in_stock, -s.final))
    return suggestions


def co_interest_counts(product):
    """{other product id: number of logged-in shoppers who interacted with both}."""
    shoppers = Interaction.objects.filter(product=product, user__isnull=False).values("user")
    rows = (Interaction.objects.filter(user__in=shoppers).exclude(product=product)
            .values("product_id").annotate(shoppers=Count("user", distinct=True)))
    return {row["product_id"]: row["shoppers"] for row in rows}


def _load(pairs, source):
    products = Product.objects.filter(id__in=[pid for pid, _ in pairs], is_active=True).select_related("category")
    by_id = {p.id: p for p in products}
    return [Suggestion(by_id[pid], score, source) for pid, score in pairs if pid in by_id]


# --------------------------------------------------------------- training
def train_and_save(k=None, k_min=None, k_max=None):
    """Train on the current catalog, save the next Joblib version and record it. Returns (bundle, path, run).

    Used by both `manage.py train_recommender` and the dashboard's Retrain button.
    """
    frame = features.load_product_frame()
    if len(frame) < 4:
        raise ValueError("Need at least 4 active products to train. Run: python manage.py seed_data")
    bundle = engine.train(frame, k=k, k_min=k_min, k_max=k_max)
    path = engine.save(bundle)
    run = save_training_results(bundle, path)
    engine.reset_cache()  # the running site picks up the new version on its next request
    cache.delete("recommender:popularity")
    return bundle, path, run


def products_missing_from_model():
    """Active products the current model doesn't know yet (added after the last training)."""
    recommender = engine.get_recommender()
    active = set(Product.objects.filter(is_active=True).values_list("id", flat=True))
    return len(active) if recommender is None else len([pid for pid in active if pid not in recommender])


# --------------------------------------------------------------- A/B test
def ab_test_enabled():
    """On only if the code allows it (settings) and the admin hasn't switched it off (dashboard)."""
    return settings.RECOMMENDER["AB_TEST_ENABLED"] and RecommenderSettings.current().ab_test_enabled


def ab_variant(request):
    """'A' (pure similarity) or 'B' (hybrid ranking), stable for each shopper; '-' when the test is off.

    The variant comes from an MD5 hash of the user id (or the guest's session key), so the same
    person always sees the same variant and shoppers split roughly 50/50.
    """
    if not ab_test_enabled():
        return RecommendationEvent.Variant.NONE
    identity = f"user:{request.user.pk}" if request.user.is_authenticated else f"guest:{ensure_session_key(request)}"
    return "AB"[int(hashlib.md5(identity.encode()).hexdigest(), 16) % 2]


def ranking_for(variant):
    return "similarity" if variant == "A" else "hybrid"


# --------------------------------------------------------------- training results
@transaction.atomic
def save_training_results(bundle, model_path):
    """Record the run, cache each product's neighbours, and store every feature vector."""
    run = TrainingRun.objects.create(
        version=bundle["version"], k=bundle["k"], silhouette=bundle["silhouette"],
        k_scores=bundle["k_scores"], cluster_sizes={str(c): n for c, n in bundle["cluster_sizes"].items()},
        n_products=len(bundle["product_ids"]), n_features=bundle["matrix"].shape[1],
        model_file=model_path.name, duration_seconds=bundle["duration_seconds"],
    )
    RecommendationData.objects.all().delete()
    RecommendationData.objects.bulk_create([
        RecommendationData(product_id=product_id, cluster_id=cluster, similar_ids=ids, similar_scores=scores,
                           model_version=run.version)
        for product_id, cluster, ids, scores in zip(bundle["product_ids"], bundle["labels"], bundle["top_ids"],
                                                    bundle["top_scores"])
    ])
    products = list(Product.objects.filter(id__in=bundle["product_ids"]).only("id"))
    rows = {product_id: row for row, product_id in enumerate(bundle["product_ids"])}
    for product in products:
        product.feature_vector = bundle["matrix"][rows[product.id]].round(VECTOR_DECIMALS).tolist()
    Product.objects.bulk_update(products, ["feature_vector"], batch_size=200)
    return run


# --------------------------------------------------------------- serving
def similar_products(product, limit=None, ranking="hybrid"):
    """'You may also like' for a product, ranked by the hybrid score, each with its 'Why this?' reasons.

    Candidates are the model's nearest neighbours; a product added after training falls back to
    popular products from its category. Out-of-stock products always go last.
    """
    limit = limit or settings.RECOMMENDER["TOP_N"]
    recommender = engine.get_recommender()
    if recommender and product.id in recommender:
        suggestions = _load(recommender.similar(product.id, settings.RECOMMENDER["CACHE_TOP_N"]), "model")
    else:
        popular = (Product.objects.filter(category=product.category, is_active=True).exclude(pk=product.pk)
                   .order_by("-rating_count", "-rating_avg").values_list("id", flat=True)[:limit * 2])
        suggestions = _load([(pid, None) for pid in popular], "fallback")

    chosen = _rank(suggestions, ranking)[:limit]
    popularity, co_interest = popularity_scores(), co_interest_counts(product)
    # Only the few strongest overlaps get "Popular with shoppers like you"; a chip on every card means nothing.
    by_overlap = sorted(chosen, key=lambda s: -co_interest.get(s.product.id, 0))  # ties keep ranking order
    strongest = {s.product.id for s in by_overlap[:SHOPPERS_LIKE_YOU_TOP]}
    for s in chosen:
        overlap = co_interest.get(s.product.id, 0) if s.product.id in strongest else 0
        s.reasons = explain.similar_reasons(product, s.product, overlap, popularity.get(s.product.id, 0.0))
    return chosen


def trending_suggestions(limit=None):
    limit = limit or settings.RECOMMENDER["TOP_N"]
    return [Suggestion(p, None, "trending", reasons=["Trending"]) for p in trending_products(limit=limit)]


def recommended_for(user, limit=None):
    """'Recommended for you'. Returns (mode, suggestions) where mode is 'personal' or 'trending'.

    The shopper's recent interactions (weighted by type and by how recent they are) are averaged
    into one taste vector; products closest to it are ranked with the hybrid score. Products they
    have already bought or looked at are left out, so the feed shows something new.
    """
    limit = limit or settings.RECOMMENDER["TOP_N"]
    recommender = engine.get_recommender()
    if recommender is None or not user.is_authenticated:
        return "trending", trending_suggestions(limit)

    recent = list(Interaction.objects.filter(user=user).order_by("-timestamp")
                  .values_list("product_id", "interaction_type", "timestamp")[:PROFILE_SIZE])
    now = timezone.now()
    vectors, weights, seen = [], [], set()
    for product_id, kind, when in recent:
        seen.add(product_id)
        if product_id in recommender:
            decay = 0.5 ** ((now - when).days / PROFILE_HALF_LIFE_DAYS)  # half the weight every 30 days
            vectors.append(recommender.vector(product_id))
            weights.append(settings.INTERACTION_WEIGHTS.get(kind, 1) * decay)
    if not vectors:
        return "trending", trending_suggestions(limit)

    profile = engine.profile_vector(vectors, weights)
    purchased = set(OrderItem.objects.filter(order__user=user).values_list("product_id", flat=True))
    candidates = recommender.nearest_to(profile, exclude=seen | purchased, n=PERSONAL_CANDIDATES)
    chosen = _rank(_load(candidates, "personal"))[:limit]

    viewed = {p.id: p for p in Product.objects.filter(id__in=[pid for pid in seen if pid in recommender])}
    popularity = popularity_scores()
    for s in chosen:
        # Name the viewed product this suggestion is most similar to.
        closest = max(viewed.values(), key=lambda v: float(recommender.vector(v.id) @ recommender.vector(s.product.id)))
        s.reasons = explain.personal_reasons(s.product, closest, popularity.get(s.product.id, 0.0))
    return "personal", chosen


def frequently_bought_together(product_ids, limit=4):
    """Products that appear in the same orders as `product_ids` (counted per order), excluding those ids.

    If nobody has bought them together yet, fall back to products similar to the first one.
    """
    product_ids = list(product_ids)
    if not product_ids:
        return []
    orders = OrderItem.objects.filter(product_id__in=product_ids).values("order_id")
    rows = (OrderItem.objects.filter(order_id__in=orders).exclude(product_id__in=product_ids)
            .values("product_id").annotate(orders=Count("order_id", distinct=True))
            .order_by("-orders", "product_id")[:limit * 2])
    counts = {row["product_id"]: row["orders"] for row in rows}
    suggestions = _load([(pid, None) for pid in counts], "fbt")
    if not suggestions:
        first = Product.objects.filter(pk=product_ids[0]).first()
        similar = similar_products(first, limit=limit * 2) if first else []
        return [s for s in similar if s.product.id not in product_ids][:limit]
    for s in suggestions:
        s.together = counts[s.product.id]
        s.reasons = explain.together_reasons(s.together)
    suggestions.sort(key=lambda s: (not s.product.in_stock, -s.together))
    return suggestions[:limit]


def model_version():
    recommender = engine.get_recommender()
    return recommender.version if recommender else None


# --------------------------------------------------------------- impressions and clicks
def _who(request):
    user = request.user if request.user.is_authenticated else None
    return {"user": user, "session_key": ensure_session_key(request)}


def log_impressions(request, products, widget, source_product=None, variant=RecommendationEvent.Variant.NONE):
    """One 'impression' row per recommended product shown. CTR = clicks / impressions."""
    who = _who(request)
    RecommendationEvent.objects.bulk_create([
        RecommendationEvent(event_type=RecommendationEvent.EventType.IMPRESSION, widget=widget, variant=variant,
                            product=product, source_product=source_product, **who)
        for product in products
    ])


def log_click(request, product, widget, source_product_id=None, variant=RecommendationEvent.Variant.NONE):
    if widget not in WIDGETS:
        return
    source = None
    if str(source_product_id or "").isdigit():  # comes from the URL, so never trust it blindly
        source = Product.objects.filter(pk=int(source_product_id)).first()
    valid_variants = {choice.value for choice in RecommendationEvent.Variant}
    RecommendationEvent.objects.create(
        event_type=RecommendationEvent.EventType.CLICK, widget=widget,
        variant=variant if variant in valid_variants else RecommendationEvent.Variant.NONE,
        product=product, source_product=source, **_who(request))
