from django.contrib import admin

from .models import RecommendationData, RecommendationEvent, TrainingRun


@admin.register(TrainingRun)
class TrainingRunAdmin(admin.ModelAdmin):
    list_display = ("version", "k", "silhouette", "n_products", "n_features", "duration_seconds", "trained_at")
    readonly_fields = [f.name for f in TrainingRun._meta.fields]


@admin.register(RecommendationData)
class RecommendationDataAdmin(admin.ModelAdmin):
    list_display = ("product", "cluster_id", "model_version", "updated_at")
    list_filter = ("cluster_id", "model_version")
    search_fields = ("product__name",)
    list_select_related = ("product",)


@admin.register(RecommendationEvent)
class RecommendationEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event_type", "widget", "variant", "product", "user")
    list_filter = ("event_type", "widget", "variant")
    list_select_related = ("product", "user")
    date_hierarchy = "created_at"
