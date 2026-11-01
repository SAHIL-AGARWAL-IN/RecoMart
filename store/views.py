"""Storefront pages. Views stay thin: queries and rules live in services.py."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from recommender import services as rec_services

from . import cart as cart_service
from . import services
from .forms import CheckoutForm, ReviewForm
from .models import Category, Interaction, Order, Product, Review

# The home hero draws three product "clusters", a picture of what K-Means does.
# Positions are percentages of a square box: label (x, y) and three product nodes.
HERO_LAYOUT = [
    {"category": "electronics", "label": (28, 5), "nodes": [(16, 19), (40, 21), (26, 45)]},
    {"category": "fashion", "label": (85, 12), "nodes": [(67, 22), (88, 35), (70, 54)]},
    {"category": "beauty", "label": (77, 87), "nodes": [(30, 72), (56, 70), (47, 91)]},
]
# Dashed lines between neighbouring clusters: (cluster, node) -> (cluster, node)
HERO_BRIDGES = [((0, 1), (1, 0)), ((0, 2), (2, 0)), ((1, 2), (2, 1))]


def _hero_clusters():
    """Top-rated products from three categories, positioned for the hero's cluster map."""
    clusters = []
    for layout in HERO_LAYOUT:
        products = list(Product.objects.filter(category__slug=layout["category"], is_active=True, stock__gt=0)
                        .select_related("category").exclude(image="")
                        .order_by("-rating_avg", "-rating_count")[:3])
        if len(products) < 3:
            return {}
        nodes = [{"product": p, "x": x, "y": y} for p, (x, y) in zip(products, layout["nodes"])]
        points = layout["nodes"]
        clusters.append({
            "name": products[0].category.name,
            "label_x": layout["label"][0],
            "label_y": layout["label"][1],
            "nodes": nodes,
            "edges": [(*points[a], *points[b]) for a, b in ((0, 1), (1, 2), (2, 0))],
            "cx": sum(x for x, _ in points) / 3,
            "cy": sum(y for _, y in points) / 3,
        })
    bridges = [(*HERO_LAYOUT[c1]["nodes"][n1], *HERO_LAYOUT[c2]["nodes"][n2]) for (c1, n1), (c2, n2) in HERO_BRIDGES]
    return {"clusters": clusters, "bridges": bridges}


def home(request):
    # Explicit order_by: Django ignores Meta.ordering on GROUP BY (annotate + Count) queries.
    categories = (Category.objects.annotate(product_count=Count("products", filter=Q(products__is_active=True)))
                  .order_by("sort_order", "name"))
    return render(request, "store/home.html", {
        "categories": categories,
        "hero": _hero_clusters(),
        "product_total": Product.objects.filter(is_active=True).count(),
        # 10 and 5 fill two rows of 5 on wide screens; extra cards are hidden on narrower ones.
        "trending": services.trending_products(limit=10),
        "deals": services.deal_products(limit=5),
    })


def product_list(request, slug=None):
    category = get_object_or_404(Category, slug=slug) if slug else None
    filters = services.parse_filters(request.GET, category=category)
    page = Paginator(services.filter_products(filters), services.PRODUCTS_PER_PAGE).get_page(request.GET.get("page"))
    return render(request, "store/product_list.html", {
        "category": category,
        "categories": Category.objects.all(),
        "filters": filters,
        "sort_options": [(key, label) for key, (label, _) in services.SORT_OPTIONS.items()],
        "page": page,
        "has_filters": any([filters["q"], filters["min_price"], filters["max_price"], filters["rating"],
                            filters["category"] and not category]),
    })


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related("images"), slug=slug, is_active=True)

    # Opened from a recommendation (?rec=similar&src=12): count the click, then redirect to the
    # clean URL so refreshing or sharing the page doesn't count it again.
    if "rec" in request.GET:
        rec_services.log_click(request, product, request.GET["rec"], request.GET.get("src"), request.GET.get("v", "-"))
        return redirect(product.get_absolute_url())

    services.log_interaction(request, product, Interaction.Type.VIEW)
    services.remember_viewed(request, product)

    reviews = product.reviews.select_related("user")
    counts = dict(reviews.values_list("rating").annotate(n=Count("id")).values_list("rating", "n"))
    total = sum(counts.values())
    breakdown = [{"stars": s, "count": counts.get(s, 0), "percent": round(100 * counts.get(s, 0) / total) if total else 0}
                 for s in range(5, 0, -1)]
    gallery = [product.image.url] if product.image else []
    gallery += [image.image.url for image in product.images.all()]
    my_review = reviews.filter(user=request.user).first() if request.user.is_authenticated else None

    return render(request, "store/product_detail.html", {
        "product": product,
        "gallery": gallery,
        "reviews": reviews[:10],
        "verified_ids": set(Order.objects.filter(items__product=product).values_list("user_id", flat=True)),
        "breakdown": breakdown,
        "savings": product.price - product.effective_price,
        "free_shipping_threshold": services.FREE_SHIPPING_THRESHOLD,
        "review_form": ReviewForm(instance=my_review),
        "my_review": my_review,
    })


@login_required
@require_POST
def submit_review(request, slug):
    """Create or update the shopper's one review of this product."""
    product = get_object_or_404(Product, slug=slug, is_active=True)
    existing = Review.objects.filter(user=request.user, product=product).first()
    form = ReviewForm(request.POST, instance=existing)
    if form.is_valid():
        review = form.save(commit=False)
        review.user, review.product = request.user, product
        review.save()  # Review.save() also refreshes the product's average rating
        if existing is None:
            services.log_interaction(request, product, Interaction.Type.REVIEW)
        messages.success(request, "Review updated." if existing else "Thanks! Your review is posted.")
    else:
        messages.error(request, "Choose a star rating from 1 to 5 to post your review.")
    return redirect(f"{product.get_absolute_url()}#reviews")


def cart(request):
    totals = cart_service.summary(cart_service.get_cart(request))
    return render(request, "store/cart.html", {"totals": totals})


@login_required
def checkout(request):
    current = cart_service.get_cart(request)
    totals = cart_service.summary(current)
    if not totals["items"]:
        messages.info(request, "Your cart is empty. Add something before checking out.")
        return redirect("store:cart")

    form = CheckoutForm(request.POST or None, initial=_checkout_initial(request.user))
    if request.method == "POST" and form.is_valid():
        try:
            order = services.place_order(request.user, current, form.shipping_data(),
                                         form.cleaned_data["payment_method"], form.payment_detail())
        except services.OutOfStockError as error:
            messages.error(request, str(error))
            return redirect("store:cart")
        return redirect("store:order_success", pk=order.pk)
    return render(request, "store/checkout.html", {"form": form, "totals": totals})


def _checkout_initial(user):
    """Prefill the address from the shopper's last order, or the name from their profile."""
    last = user.orders.first()
    if last:
        return {field: getattr(last, field) for field in CheckoutForm.SHIPPING_FIELDS}
    return {"full_name": user.get_full_name(), "phone": user.phone}


@login_required
def order_success(request, pk):
    order = get_object_or_404(Order.objects.prefetch_related("items__product"), pk=pk, user=request.user)
    return render(request, "store/order_success.html", {"order": order})


@login_required
def order_detail(request, pk):
    # Filtering by user=request.user makes other people's orders a 404, so nothing leaks.
    order = get_object_or_404(Order.objects.prefetch_related("items__product"), pk=pk, user=request.user)
    statuses = [value for value, _ in Order.Status.choices]
    reached = statuses.index(order.status)
    timeline = [{"label": label, "done": index <= reached} for index, (_, label) in enumerate(Order.Status.choices)]
    return render(request, "store/order_detail.html", {"order": order, "timeline": timeline})


@login_required
def wishlist(request):
    items = request.user.wishlist_items.select_related("product", "product__category")
    return render(request, "store/wishlist.html", {"products": [item.product for item in items]})


@login_required
def order_list(request):
    orders = request.user.orders.prefetch_related("items__product")
    return render(request, "store/order_list.html", {"orders": orders})
