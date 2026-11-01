"""'Why this?' chips: short, rule-based reasons shown on each recommendation card.

They are checked in a fixed order and at most two are shown, so the most useful reason
comes first. They describe the recommendation; they don't change the ranking.
"""
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

MAX_REASONS = 2
SIMILAR_PRICE_RANGE = Decimal("0.25")   # within ±25% of the product being viewed (prices are Decimals)
TOP_RATED = 4.5
TRENDING = 0.8               # popularity score (0..1) at or above this counts as trending
NEW_ARRIVAL_DAYS = 30
SHOPPERS_LIKE_YOU = 2        # at least this many shoppers looked at both products


def _similar_price(a, b):
    return abs(b.effective_price - a.effective_price) <= a.effective_price * SIMILAR_PRICE_RANGE


def _is_new(product):
    return product.created_at >= timezone.now() - timedelta(days=NEW_ARRIVAL_DAYS)


def _quality_reasons(candidate, popularity):
    reasons = []
    if candidate.rating_avg >= TOP_RATED:
        reasons.append("Top rated")
    if popularity >= TRENDING:
        reasons.append("Trending")
    if _is_new(candidate):
        reasons.append("New arrival")
    return reasons


def similar_reasons(source, candidate, co_interest=0, popularity=0.0):
    """Reasons for 'You may also like' on the page of `source`."""
    reasons = []
    if candidate.brand and candidate.brand == source.brand:
        reasons.append("Same brand")
    if co_interest >= SHOPPERS_LIKE_YOU:
        reasons.append("Popular with shoppers like you")
    if _similar_price(source, candidate):
        reasons.append("Similar price")
    reasons += _quality_reasons(candidate, popularity)
    if not reasons:
        reasons.append("Same category" if candidate.category_id == source.category_id else "Related pick")
    return reasons[:MAX_REASONS]


def personal_reasons(candidate, because_of, popularity=0.0):
    """Reasons for 'Recommended for you': which product it resembles, plus one quality signal."""
    name = because_of.name if len(because_of.name) <= 28 else because_of.name[:27].rstrip() + "…"
    return ([f"Because you viewed {name}"] + _quality_reasons(candidate, popularity))[:MAX_REASONS]


def together_reasons(times):
    """Short enough to fit a narrow card: "Bought together ×2" means in two orders."""
    return [f"Bought together ×{times}"]
