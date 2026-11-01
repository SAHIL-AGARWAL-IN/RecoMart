"""Storefront pages. Views stay thin: queries and rules live in services.py."""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render

from . import services
from .cart import get_cart
from .models import Category, Interaction, Product

PRODUCTS_PER_PAGE = 20  # divisible by 4 and 5, so full rows at both grid widths

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
    page = Paginator(services.filter_products(filters), PRODUCTS_PER_PAGE).get_page(request.GET.get("page"))
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

    services.log_interaction(request, product, Interaction.Type.VIEW)
    services.remember_viewed(request, product)

    reviews = product.reviews.select_related("user")
    counts = dict(reviews.values_list("rating").annotate(n=Count("id")).values_list("rating", "n"))
    total = sum(counts.values())
    breakdown = [{"stars": s, "count": counts.get(s, 0), "percent": round(100 * counts.get(s, 0) / total) if total else 0}
                 for s in range(5, 0, -1)]
    gallery = [product.image.url] if product.image else []
    gallery += [image.image.url for image in product.images.all()]

    return render(request, "store/product_detail.html", {
        "product": product,
        "gallery": gallery,
        "reviews": reviews[:10],
        "breakdown": breakdown,
        "savings": product.price - product.effective_price,
        "free_shipping_threshold": services.FREE_SHIPPING_THRESHOLD,
    })


def cart(request):
    """Read-only cart for now; adding, updating and removing items arrives in Phase 3."""
    current = get_cart(request)
    items = current.items.select_related("product", "product__category") if current else []
    return render(request, "store/cart.html", {
        "items": items,
        "subtotal": current.subtotal if current else 0,
    })


@login_required
def wishlist(request):
    items = request.user.wishlist_items.select_related("product", "product__category")
    return render(request, "store/wishlist.html", {"products": [item.product for item in items]})


@login_required
def order_list(request):
    orders = request.user.orders.prefetch_related("items__product")
    return render(request, "store/order_list.html", {"orders": orders})
