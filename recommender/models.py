from django.conf import settings
from django.db import models
from django.utils import timezone

from store.models import Product


class RecommendationData(models.Model):
    """Training output for one product: its cluster and its cached most-similar products."""

    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="recommendation_data")
    cluster_id = models.PositiveSmallIntegerField()
    similar_ids = models.JSONField(default=list, help_text="Product ids, most similar first")
    similar_scores = models.JSONField(default=list, help_text="Cosine similarity for each id")
    model_version = models.PositiveIntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "recommendation data"

    def __str__(self):
        return f"{self.product} → cluster {self.cluster_id} (v{self.model_version})"


class TrainingRun(models.Model):
    """One run of `train_recommender`, with the metrics shown on the ML Insights page."""

    version = models.PositiveIntegerField(unique=True)
    k = models.PositiveSmallIntegerField(help_text="Number of K-Means clusters chosen")
    silhouette = models.FloatField()
    k_scores = models.JSONField(default=list, help_text="[{k, inertia, silhouette}, ...] for every K tried")
    cluster_sizes = models.JSONField(default=dict)
    n_products = models.PositiveIntegerField()
    n_features = models.PositiveIntegerField()
    model_file = models.CharField(max_length=255)
    duration_seconds = models.FloatField(default=0)
    trained_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-version"]

    def __str__(self):
        return f"v{self.version}: K={self.k}, silhouette={self.silhouette:.3f}"


class RecommenderSettings(models.Model):
    """Switches the admin can flip on the ML Insights page (one row only)."""

    ab_test_enabled = models.BooleanField(
        default=True, help_text="Split shoppers 50/50: A sees pure similarity, B sees hybrid ranking.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "recommender settings"

    def __str__(self):
        return f"A/B test {'on' if self.ab_test_enabled else 'off'}"

    @classmethod
    def current(cls):
        settings_row, _ = cls.objects.get_or_create(pk=1)
        return settings_row


class RecommendationEvent(models.Model):
    """An impression (we showed a recommended item) or a click (the shopper opened it).

    Click-through rate (CTR) = clicks / impressions, and it is compared between A/B variants.
    """

    class Widget(models.TextChoices):
        SIMILAR = "similar", "You may also like"
        FOR_YOU = "for_you", "Recommended for you"
        TRENDING = "trending", "Trending now"
        FBT = "fbt", "Frequently bought together"

    class Variant(models.TextChoices):
        A = "A", "A: similar items"
        B = "B", "B: hybrid ranking"
        NONE = "-", "Not in test"

    class EventType(models.TextChoices):
        IMPRESSION = "impression", "Impression"
        CLICK = "click", "Click"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="recommendation_events")
    session_key = models.CharField(max_length=40, blank=True)
    widget = models.CharField(max_length=10, choices=Widget.choices)
    variant = models.CharField(max_length=1, choices=Variant.choices, default=Variant.NONE)
    event_type = models.CharField(max_length=10, choices=EventType.choices)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="recommendation_events")
    source_product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True, related_name="+",
                                       help_text="The product page the recommendation was shown on, if any")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["widget", "variant", "event_type"])]

    def __str__(self):
        return f"{self.event_type} {self.widget}/{self.variant} {self.product}"
