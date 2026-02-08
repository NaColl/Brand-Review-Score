"""Dimension 8 — Pricing Intelligence Score.

Tracks pricing health through sale percentages, discount depth,
resale value tracking, and price sentiment from reviews.

Components:
    1. Sale Percentage (30%) — % of products on sale (low = healthy demand)
    2. Discount Depth (20%) — Average discount (shallow = strong pricing power)
    3. Resale Value Ratio (30%) — Resale price / retail price
    4. Price Sentiment (20%) — Review language about pricing

Key insight from BoF intelligence:
"If 40% of a brand's new collection is in the sale section within 30 days,
their brand heat is dying."
"""

from __future__ import annotations

from config.settings import PRICING_WEIGHTS, PRICE_POSITIVE_PHRASES, PRICE_NEGATIVE_PHRASES
from src.models.review import ReviewCollection
from src.models.score import PricingIntelligenceScore


def calculate_pricing_intelligence(
    collection: ReviewCollection,
    sale_percentage: float | None = None,
    avg_discount_pct: float | None = None,
    resale_value_ratio: float | None = None,
) -> PricingIntelligenceScore:
    """Calculate Pricing Intelligence Score.

    Args:
        collection: Reviews with sentiment for price language analysis.
        sale_percentage: % of products currently on sale (0.0 to 1.0).
        avg_discount_pct: Average discount percentage (0.0 to 1.0).
        resale_value_ratio: Resale price / retail price ratio.
    """
    components: dict[str, float] = {}

    # 1. Sale Percentage — LOW is good (strong demand, no need to discount)
    components["sale_percentage"] = _sale_percentage_score(sale_percentage)

    # 2. Discount Depth — SHALLOW is good (pricing power)
    components["discount_depth"] = _discount_depth_score(avg_discount_pct)

    # 3. Resale Value Ratio — HIGH is good (brand equity)
    components["resale_value_ratio"] = _resale_value_score(resale_value_ratio)

    # 4. Price Sentiment — from review text
    components["price_sentiment"] = _price_sentiment(collection)

    value = sum(components[k] * PRICING_WEIGHTS[k] * 100 for k in PRICING_WEIGHTS)

    explanation = _build_explanation(
        components, sale_percentage, avg_discount_pct, resale_value_ratio
    )

    return PricingIntelligenceScore(
        value=value,
        components=components,
        explanation=explanation,
    )


def _sale_percentage_score(sale_pct: float | None) -> float:
    """Lower sale percentage = healthier brand.

    < 10% on sale = excellent (strong full-price sell-through)
    10-20% = healthy
    20-30% = concerning
    30-40% = weak
    > 40% = brand heat dying (per BoF intelligence)
    """
    if sale_pct is None:
        return 0.5  # No data

    if sale_pct <= 0.10:
        return 1.0
    elif sale_pct <= 0.20:
        return 0.8
    elif sale_pct <= 0.30:
        return 0.6
    elif sale_pct <= 0.40:
        return 0.35
    elif sale_pct <= 0.50:
        return 0.2
    else:
        return 0.1  # Desperate discounting


def _discount_depth_score(avg_discount: float | None) -> float:
    """Shallower discounts = stronger pricing power.

    < 15% off = strong (luxury brands rarely go below this)
    15-30% off = normal
    30-50% off = concerning
    > 50% off = desperate
    """
    if avg_discount is None:
        return 0.5

    if avg_discount <= 0.15:
        return 1.0
    elif avg_discount <= 0.25:
        return 0.75
    elif avg_discount <= 0.35:
        return 0.55
    elif avg_discount <= 0.50:
        return 0.35
    else:
        return 0.15


def _resale_value_score(ratio: float | None) -> float:
    """Map resale value ratio to score.

    > 1.2 = appreciating (Hermès, Rolex)
    1.0-1.2 = holds value perfectly
    0.7-1.0 = normal depreciation
    0.5-0.7 = below average
    < 0.5 = significant brand equity loss
    """
    if ratio is None:
        return 0.5

    if ratio >= 1.2:
        return 1.0
    elif ratio >= 1.0:
        return 0.85
    elif ratio >= 0.8:
        return 0.7
    elif ratio >= 0.6:
        return 0.5
    elif ratio >= 0.4:
        return 0.3
    else:
        return 0.1


def _price_sentiment(collection: ReviewCollection) -> float:
    if not collection.reviews:
        return 0.5

    positive = 0
    negative = 0
    for review in collection.reviews:
        lower = review.text.lower()
        if any(p in lower for p in PRICE_POSITIVE_PHRASES):
            positive += 1
        if any(p in lower for p in PRICE_NEGATIVE_PHRASES):
            negative += 1

    total = positive + negative
    if total == 0:
        return 0.5
    return positive / total


def _build_explanation(
    components: dict[str, float],
    sale_pct: float | None,
    avg_discount: float | None,
    resale_ratio: float | None,
) -> str:
    parts = []

    if sale_pct is not None:
        parts.append(f"Sale %: {sale_pct:.0%}")
        if sale_pct > 0.40:
            parts.append("ALERT: >40% on sale")
    else:
        parts.append("Sale %: no data")

    if avg_discount is not None:
        parts.append(f"Avg discount: {avg_discount:.0%}")
    if resale_ratio is not None:
        if resale_ratio >= 1.0:
            parts.append(f"Resale: {resale_ratio:.0%} (appreciating)")
        else:
            parts.append(f"Resale: {resale_ratio:.0%} (depreciating)")

    ps = components["price_sentiment"]
    parts.append(f"Price sentiment: {'positive' if ps > 0.6 else 'negative' if ps < 0.4 else 'neutral'}")

    return "; ".join(parts)
