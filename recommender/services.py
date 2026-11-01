"""Database glue for the recommender: saving training results, serving recommendations, logging events.

The ML maths lives in engine.py; this file connects it to Django models.
"""
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction

from store.models import Product
from store.services import ensure_session_key

from . import engine
from .models import RecommendationData, RecommendationEvent, TrainingRun

WIDGETS = {choice.value for choice in RecommendationEvent.Widget}
VECTOR_DECIMALS = 5


@dataclass
class Suggestion:
    product: Product
    score: float | None  # cosine similarity, or None for fallback suggestions
    source: str          # "model" or "fallback"


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
def similar_products(product, limit=None):
    """'You may also like' for a product: model neighbours, or same-category favourites as a fallback.

    Out-of-stock products are moved to the end, so shoppers see things they can buy first.
    """
    limit = limit or settings.RECOMMENDER["TOP_N"]
    recommender = engine.get_recommender()
    if recommender and product.id in recommender:
        pairs = recommender.similar(product.id, settings.RECOMMENDER["CACHE_TOP_N"])
        source = "model"
    else:
        # Not in the trained model (e.g. added after training): show popular items from its category.
        popular = (Product.objects.filter(category=product.category, is_active=True).exclude(pk=product.pk)
                   .order_by("-rating_count", "-rating_avg").values_list("id", flat=True)[:limit * 2])
        pairs = [(pid, None) for pid in popular]
        source = "fallback"

    products = Product.objects.filter(id__in=[pid for pid, _ in pairs], is_active=True).select_related("category")
    by_id = {p.id: p for p in products}
    suggestions = [Suggestion(by_id[pid], score, source) for pid, score in pairs if pid in by_id]
    suggestions.sort(key=lambda s: not s.product.in_stock)  # stable sort keeps similarity order otherwise
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
