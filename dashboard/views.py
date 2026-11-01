"""Admin dashboard: overview, product/category/order CRUD, inventory and ML Insights.

Storefront pages use function-based views; the CRUD pages here use Django's generic
class-based views (ListView, CreateView, ...) because they are the same pattern repeated.
"""
from django.conf import settings
from django.contrib import messages
from django.db.models import Count, F, ProtectedError, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from accounts.decorators import StoreAdminRequiredMixin, admin_required
from recommender import engine
from recommender import services as rec_services
from recommender.models import RecommenderSettings, TrainingRun
from store.models import Category, Order, Product

from . import analytics
from .forms import CategoryForm, OrderStatusForm, ProductForm, RestockForm


# ------------------------------------------------------------------- overview
@admin_required
def index(request):
    return render(request, "dashboard/index.html", {
        "kpis": analytics.kpis(days=30),
        "daily": analytics.daily_sales(days=30),
        "top_products": analytics.top_products(limit=8),
        "categories": analytics.revenue_by_category(),
        "statuses": analytics.status_counts(),
        "recent_orders": Order.objects.select_related("user")[:6],
    })


# ------------------------------------------------------------------- products
class ProductListView(StoreAdminRequiredMixin, ListView):
    template_name = "dashboard/product_list.html"
    paginate_by = 20

    def get_queryset(self):
        products = Product.objects.select_related("category").order_by("name")
        query = self.request.GET.get("q", "").strip()
        if query:
            products = products.filter(Q(name__icontains=query) | Q(brand__icontains=query))
        if self.request.GET.get("category"):
            products = products.filter(category__slug=self.request.GET["category"])
        return products

    def get_context_data(self, **kwargs):
        return super().get_context_data(categories=Category.objects.all(), **kwargs)


class ProductCreateView(StoreAdminRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = "dashboard/form.html"
    success_url = reverse_lazy("dashboard:products")
    extra_context = {"title": "Add product", "back_url": reverse_lazy("dashboard:products")}

    def form_valid(self, form):
        messages.success(self.request, f"Added {form.instance.name}. Retrain the model to include it in recommendations.")
        return super().form_valid(form)


class ProductUpdateView(StoreAdminRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "dashboard/form.html"
    success_url = reverse_lazy("dashboard:products")
    extra_context = {"title": "Edit product", "back_url": reverse_lazy("dashboard:products")}

    def form_valid(self, form):
        messages.success(self.request, f"Saved {form.instance.name}.")
        return super().form_valid(form)


class ProductDeleteView(StoreAdminRequiredMixin, DeleteView):
    model = Product
    template_name = "dashboard/confirm_delete.html"
    success_url = reverse_lazy("dashboard:products")
    extra_context = {"back_url": reverse_lazy("dashboard:products")}

    def form_valid(self, form):
        product = self.get_object()
        try:
            product.delete()
            messages.success(self.request, f"Deleted {product.name}.")
        except ProtectedError:
            # Old orders point at this product (on_delete=PROTECT), so hide it instead of deleting it.
            product.is_active = False
            product.save(update_fields=["is_active"])
            messages.info(self.request, f"{product.name} appears in past orders, so it was hidden from the store instead.")
        return redirect(self.success_url)


# ------------------------------------------------------------------- categories
class CategoryListView(StoreAdminRequiredMixin, ListView):
    template_name = "dashboard/category_list.html"

    def get_queryset(self):
        return Category.objects.annotate(product_count=Count("products")).order_by("sort_order", "name")


class CategoryCreateView(StoreAdminRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "dashboard/form.html"
    success_url = reverse_lazy("dashboard:categories")
    extra_context = {"title": "Add category", "back_url": reverse_lazy("dashboard:categories")}


class CategoryUpdateView(StoreAdminRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "dashboard/form.html"
    success_url = reverse_lazy("dashboard:categories")
    extra_context = {"title": "Edit category", "back_url": reverse_lazy("dashboard:categories")}


class CategoryDeleteView(StoreAdminRequiredMixin, DeleteView):
    model = Category
    template_name = "dashboard/confirm_delete.html"
    success_url = reverse_lazy("dashboard:categories")
    extra_context = {"back_url": reverse_lazy("dashboard:categories")}

    def form_valid(self, form):
        category = self.get_object()
        try:
            category.delete()
            messages.success(self.request, f"Deleted {category.name}.")
        except ProtectedError:
            messages.error(self.request, f"{category.name} still has products. Move or delete them first.")
        return redirect(self.success_url)


# ------------------------------------------------------------------- orders
class OrderListView(StoreAdminRequiredMixin, ListView):
    template_name = "dashboard/order_list.html"
    paginate_by = 25

    def get_queryset(self):
        orders = Order.objects.select_related("user")
        status = self.request.GET.get("status")
        if status in Order.Status.values:
            orders = orders.filter(status=status)
        query = self.request.GET.get("q", "").strip().upper().removeprefix("RM-")
        if query:
            orders = orders.filter(Q(pk=int(query)) if query.isdigit() else Q(full_name__icontains=query)
                                   | Q(user__username__icontains=query))
        return orders

    def get_context_data(self, **kwargs):
        return super().get_context_data(statuses=Order.Status.choices, **kwargs)


class OrderDetailView(StoreAdminRequiredMixin, DetailView):
    model = Order
    template_name = "dashboard/order_detail.html"

    def get_queryset(self):
        return Order.objects.select_related("user").prefetch_related("items__product")

    def get_context_data(self, **kwargs):
        return super().get_context_data(status_form=OrderStatusForm(instance=self.object), **kwargs)


@admin_required
@require_POST
def order_status(request, pk):
    order = get_object_or_404(Order, pk=pk)
    form = OrderStatusForm(request.POST, instance=order)
    if form.is_valid():
        form.save()
        messages.success(request, f"Order {order.order_number} is now {order.get_status_display().lower()}.")
    return redirect("dashboard:order_detail", pk=pk)


# ------------------------------------------------------------------- inventory
@admin_required
def inventory(request):
    try:
        threshold = max(0, int(request.GET.get("below", analytics.LOW_STOCK)))
    except ValueError:
        threshold = analytics.LOW_STOCK
    products = Product.objects.filter(is_active=True, stock__lte=threshold).select_related("category").order_by("stock", "name")
    return render(request, "dashboard/inventory.html", {"products": products, "threshold": threshold})


@admin_required
@require_POST
def restock(request):
    form = RestockForm(request.POST)
    if form.is_valid():
        updated = Product.objects.filter(pk=form.cleaned_data["product_id"]).update(stock=F("stock") + form.cleaned_data["add"])
        if updated:
            product = Product.objects.get(pk=form.cleaned_data["product_id"])
            messages.success(request, f"{product.name} now has {product.stock} in stock.")
    else:
        messages.error(request, "Enter how many units to add (1 or more).")
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):  # no open redirects
        return redirect(next_url)
    return redirect("dashboard:inventory")


# ------------------------------------------------------------------- ML Insights
def _cluster_summary(bundle):
    """Size, main category and a few example products for each K-Means cluster."""
    products = {p.id: p for p in Product.objects.filter(id__in=bundle["product_ids"]).select_related("category")}
    clusters = {}
    for product_id, label in zip(bundle["product_ids"], bundle["labels"]):
        if product_id in products:
            clusters.setdefault(label, []).append(products[product_id])
    summary = []
    for label, members in sorted(clusters.items()):
        names = [p.category.name for p in members]
        main = max(set(names), key=names.count)
        summary.append({"id": label, "size": len(members), "main_category": main,
                        "purity_pct": round(100 * names.count(main) / len(members)),
                        "examples": [p.name for p in members[:3]]})
    return summary, products


def _scatter_points(bundle, products):
    return [{"x": float(x), "y": float(y), "c": int(label), "name": products[pid].name}
            for pid, label, (x, y) in zip(bundle["product_ids"], bundle["labels"], bundle["pca_2d"])
            if pid in products]


@admin_required
def ml_insights(request):
    run = TrainingRun.objects.first()
    recommender = engine.get_recommender()
    context = {
        "run": run,
        "ctr": analytics.ctr_by_widget(),
        "ab": analytics.ab_results(),
        "ab_enabled": rec_services.ab_test_enabled(),
        "ab_allowed": settings.RECOMMENDER["AB_TEST_ENABLED"],
        "weights": settings.RECOMMENDER["HYBRID_WEIGHTS"],
        "missing_from_model": rec_services.products_missing_from_model(),
    }
    if recommender is not None and run is not None:
        summary, products = _cluster_summary(recommender.bundle)
        context.update(clusters=summary, scatter=_scatter_points(recommender.bundle, products),
                       k_scores=run.k_scores, elbow_k=recommender.bundle.get("elbow_k"),
                       pca_variance_pct=round(100 * recommender.bundle["pca_variance"]) if "pca_variance" in recommender.bundle else None)
    return render(request, "dashboard/ml_insights.html", context)


@admin_required
@require_POST
def retrain(request):
    """Run training now (a few seconds on this catalog) and report the new metrics as JSON."""
    try:
        bundle, path, run = rec_services.train_and_save()
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    messages.success(request, f"Model v{run.version} trained: K = {run.k}, silhouette {run.silhouette:.3f}.")
    return JsonResponse({"version": run.version, "k": run.k, "silhouette": run.silhouette,
                         "n_products": run.n_products, "duration_seconds": run.duration_seconds})


@admin_required
@require_POST
def toggle_ab(request):
    settings_row = RecommenderSettings.current()
    settings_row.ab_test_enabled = request.POST.get("enabled") == "on"
    settings_row.save()
    state = "on. Shoppers are split between A and B" if settings_row.ab_test_enabled else "off. Everyone sees hybrid ranking"
    messages.success(request, f"A/B test switched {state}.")
    return redirect("dashboard:ml_insights")
