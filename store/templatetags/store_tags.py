"""Template helpers: Indian rupee formatting, star ratings and query-string links."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django import template

register = template.Library()


def indian_grouping(digits):
    """'1359999' -> '13,59,999': last 3 digits, then groups of 2 (Indian numbering)."""
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups) + "," + tail


@register.filter
def inr(value):
    """Format a number as Indian rupees: 1359999 -> ₹13,59,999 and 62.5 -> ₹62.50."""
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return ""
    sign = "-" if amount < 0 else ""
    rupees, paise = f"{abs(amount):.2f}".split(".")
    text = f"{sign}₹{indian_grouping(rupees)}"
    return text if paise == "00" else f"{text}.{paise}"


@register.inclusion_tag("partials/_stars.html")
def stars(rating, count=None, size=""):
    """Five star icons (full, half or empty) with an accessible label."""
    rating = float(rating or 0)
    icons = []
    for position in range(1, 6):
        if rating >= position - 0.25:
            icons.append("star-fill")
        elif rating >= position - 0.75:
            icons.append("star-half")
        else:
            icons.append("star")
    return {"icons": icons, "rating": rating, "count": count, "size": size}


@register.simple_tag(takes_context=True)
def query_with(context, **changes):
    """Current GET parameters with some replaced, for pagination and sort links.

    {% query_with page=3 %} -> "?q=phone&sort=price_asc&page=3"
    """
    params = context["request"].GET.copy()
    for key, value in changes.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    encoded = params.urlencode()
    return f"?{encoded}" if encoded else "?"
