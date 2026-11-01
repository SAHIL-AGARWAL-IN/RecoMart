"""Numbers for the admin dashboard, computed with Django ORM aggregates (SUM, COUNT, GROUP BY)."""
import math
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from recommender.models import RecommendationEvent
from store.models import Order, OrderItem, Product

LOW_STOCK = 5
ZERO = Decimal("0")
LINE_TOTAL = ExpressionWrapper(F("unit_price") * F("quantity"), output_field=DecimalField(max_digits=14, decimal_places=2))


def _window(days, end=None):
    end = end or timezone.now()
    return end - timedelta(days=days), end


def _change(current, previous):
    """Percentage change, or None when there's nothing to compare against."""
    if not previous:
        return None
    return round(float((current - previous) / previous * 100), 1)


# ------------------------------------------------------------------- KPIs
def kpis(days=30):
    start, end = _window(days)
    previous_start = start - timedelta(days=days)
    # Inclusive end (lte): on Windows the clock is coarse, so an order made "just now" can share
    # the exact timestamp of `end`, and a strict < would leave it out.
    now_orders = Order.objects.filter(created_at__gte=start, created_at__lte=end)
    before_orders = Order.objects.filter(created_at__gte=previous_start, created_at__lt=start)
    now = now_orders.aggregate(revenue=Sum("total"), orders=Count("id"), customers=Count("user", distinct=True))
    before = before_orders.aggregate(revenue=Sum("total"), orders=Count("id"))
    revenue, orders = now["revenue"] or ZERO, now["orders"]
    return {
        "days": days,
        "revenue": revenue,
        "revenue_change": _change(revenue, before["revenue"] or ZERO),
        "orders": orders,
        "orders_change": _change(Decimal(orders), Decimal(before["orders"])),
        "aov": (revenue / orders).quantize(Decimal("1")) if orders else ZERO,  # whole rupees
        "customers": now["customers"],
        "low_stock": Product.objects.filter(is_active=True, stock__lte=LOW_STOCK).count(),
    }


def daily_sales(days=30):
    """[{date, revenue, orders}] for every day in the window, including days with no orders."""
    start, _ = _window(days)
    rows = (Order.objects.filter(created_at__gte=start)
            .annotate(day=TruncDate("created_at")).values("day")
            .annotate(revenue=Sum("total"), orders=Count("id")))
    by_day = {row["day"]: row for row in rows}
    today = timezone.localdate()
    series = []
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        row = by_day.get(day, {})
        series.append({"date": day.isoformat(), "revenue": float(row.get("revenue") or 0), "orders": row.get("orders", 0)})
    return series


def top_products(limit=8, days=30):
    start, _ = _window(days)
    return list(OrderItem.objects.filter(order__created_at__gte=start)
                .values("product_id", "product_name")
                .annotate(units=Sum("quantity"), revenue=Sum(LINE_TOTAL))
                .order_by("-units", "-revenue")[:limit])


def revenue_by_category(days=30):
    start, _ = _window(days)
    return list(OrderItem.objects.filter(order__created_at__gte=start)
                .values(category=F("product__category__name"))
                .annotate(revenue=Sum(LINE_TOTAL), units=Sum("quantity"))
                .order_by("-revenue"))


def status_counts():
    counts = dict(Order.objects.values_list("status").annotate(n=Count("id")).values_list("status", "n"))
    return [{"status": value, "label": label, "count": counts.get(value, 0)} for value, label in Order.Status.choices]


# ------------------------------------------------------------------- recommendation metrics
def _impressions_and_clicks(queryset, field):
    rows = queryset.values(field, "event_type").annotate(n=Count("id"))
    table = {}
    for row in rows:
        table.setdefault(row[field], {"impressions": 0, "clicks": 0})
        table[row[field]]["impressions" if row["event_type"] == "impression" else "clicks"] = row["n"]
    return table


def ctr_by_widget():
    """Click-through rate (clicks ÷ impressions) for each recommendation strip."""
    table = _impressions_and_clicks(RecommendationEvent.objects.all(), "widget")
    result = []
    for value, label in RecommendationEvent.Widget.choices:
        stats = table.get(value, {"impressions": 0, "clicks": 0})
        ctr = stats["clicks"] / stats["impressions"] if stats["impressions"] else 0.0
        result.append({"widget": value, "label": label, **stats, "ctr": ctr, "ctr_pct": round(ctr * 100, 2)})
    return result


def two_proportion_z_test(clicks_a, shown_a, clicks_b, shown_b):
    """Is B's click rate really different from A's, or could it be chance?

    z = (pB - pA) / sqrt(p(1-p)(1/nA + 1/nB)), where p is the pooled click rate.
    The two-sided p-value is the chance of a difference at least this big if A and B were equal.
    """
    if not shown_a or not shown_b:
        return None
    rate_a, rate_b = clicks_a / shown_a, clicks_b / shown_b
    pooled = (clicks_a + clicks_b) / (shown_a + shown_b)
    spread = math.sqrt(pooled * (1 - pooled) * (1 / shown_a + 1 / shown_b))
    if spread == 0:
        return None
    z = (rate_b - rate_a) / spread
    p_value = math.erfc(abs(z) / math.sqrt(2))  # = 2 × (1 − Φ(|z|))
    return {"z": round(z, 3), "p_value": round(p_value, 4), "significant": p_value < 0.05,
            "lift": round((rate_b - rate_a) / rate_a * 100, 1) if rate_a else None,
            "lift_abs": round(abs(rate_b - rate_a) / rate_a * 100, 1) if rate_a else None}


def ab_results():
    """CTR of 'You may also like' for variant A (similarity) vs B (hybrid), plus the z-test."""
    table = _impressions_and_clicks(RecommendationEvent.objects.filter(widget="similar", variant__in=["A", "B"]), "variant")
    variants = []
    for value, label in (("A", "A: pure similarity"), ("B", "B: hybrid ranking")):
        stats = table.get(value, {"impressions": 0, "clicks": 0})
        ctr = stats["clicks"] / stats["impressions"] if stats["impressions"] else 0.0
        variants.append({"variant": value, "label": label, **stats, "ctr": ctr, "ctr_pct": round(ctr * 100, 2)})
    a, b = variants
    return {"variants": variants, "test": two_proportion_z_test(a["clicks"], a["impressions"], b["clicks"], b["impressions"])}
