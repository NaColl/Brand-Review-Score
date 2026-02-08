"""Dimension 3 — Value Perception Score.

Do people perceive price as fair relative to quality?

Merges the v1 Review Quality dimension with price-quality signals
and resale premium tracking.

Components:
    1. Review Rating (30%) — Time-decay weighted star average
    2. Price-Quality Sentiment (25%) — "worth it" vs "overpriced" language
    3. Review Depth (15%) — Detailed reviews signal quality engagement
    4. Resale Premium (30%) — Resale value vs retail (luxury equity proxy)
"""

from __future__ import annotations

import math
from datetime import datetime

from config.settings import (
    VALUE_WEIGHTS,
    RECENCY_DECAY_LAMBDA,
    PRICE_POSITIVE_PHRASES,
    PRICE_NEGATIVE_PHRASES,
)
from src.models.review import ReviewCollection
from src.models.score import ValuePerceptionScore


def calculate_value_perception(
    collection: ReviewCollection,
    resale_premium_ratio: float | None = None,
) -> ValuePerceptionScore:
    """Calculate the Value Perception Score.

    Args:
        collection: All reviews/mentions with sentiment and ratings.
        resale_premium_ratio: Resale price / retail price ratio.
                              >1.0 = appreciating, <1.0 = depreciating.
                              None = no resale data available.
    """
    components: dict[str, float] = {}

    # 1. Review Rating (time-decay weighted)
    components["review_rating"] = _normalized_rating(collection)

    # 2. Price-Quality Sentiment
    components["price_quality_sentiment"] = _price_quality_sentiment(collection)

    # 3. Review Depth
    components["review_depth"] = _review_depth(collection)

    # 4. Resale Premium
    components["resale_premium"] = _resale_premium_score(resale_premium_ratio)

    value = sum(components[k] * VALUE_WEIGHTS[k] * 100 for k in VALUE_WEIGHTS)

    explanation = _build_explanation(components, collection, resale_premium_ratio)

    return ValuePerceptionScore(
        value=value,
        components=components,
        explanation=explanation,
    )


def _normalized_rating(collection: ReviewCollection) -> float:
    rated = [(r.rating, r.timestamp) for r in collection.reviews if r.rating is not None]
    if not rated:
        return 0.5
    now = datetime.utcnow()
    weighted_sum = 0.0
    weight_total = 0.0
    for rating, timestamp in rated:
        days_ago = max(0, (now - timestamp).days)
        weight = math.exp(-RECENCY_DECAY_LAMBDA * days_ago)
        weighted_sum += rating * weight
        weight_total += weight
    if weight_total == 0:
        return 0.5
    avg = weighted_sum / weight_total
    return max(0.0, min(1.0, (avg - 1.0) / 4.0))


def _price_quality_sentiment(collection: ReviewCollection) -> float:
    """Ratio of positive price mentions to negative price mentions."""
    if not collection.reviews:
        return 0.5

    positive_count = 0
    negative_count = 0

    for review in collection.reviews:
        lower = review.text.lower()
        if any(phrase in lower for phrase in PRICE_POSITIVE_PHRASES):
            positive_count += 1
        if any(phrase in lower for phrase in PRICE_NEGATIVE_PHRASES):
            negative_count += 1

    total = positive_count + negative_count
    if total == 0:
        return 0.5  # No price discussion

    ratio = positive_count / total
    return ratio


def _review_depth(collection: ReviewCollection, target_words: int = 50) -> float:
    if not collection.reviews:
        return 0.0
    avg_wc = collection.average_word_count
    return 1.0 / (1.0 + math.exp(-0.1 * (avg_wc - target_words)))


def _resale_premium_score(ratio: float | None) -> float:
    """Map resale premium ratio to [0, 1].

    Ratio > 1.0 = brand appreciates (Hermès bags, Rolex watches)
    Ratio = 0.7-1.0 = normal depreciation
    Ratio < 0.5 = steep depreciation (brand equity loss)
    """
    if ratio is None:
        return 0.5  # No data

    if ratio >= 1.2:
        return 1.0  # Appreciating significantly
    elif ratio >= 1.0:
        return 0.85  # Holds value perfectly
    elif ratio >= 0.8:
        return 0.7  # Normal, healthy depreciation
    elif ratio >= 0.6:
        return 0.5  # Below average
    elif ratio >= 0.4:
        return 0.3  # Significant value loss
    else:
        return 0.1  # Brand equity collapse


def _build_explanation(
    components: dict[str, float],
    collection: ReviewCollection,
    resale_ratio: float | None,
) -> str:
    parts = []

    rr = components["review_rating"]
    star = 1.0 + rr * 4.0
    parts.append(f"Rating: {star:.1f}/5")

    pqs = components["price_quality_sentiment"]
    if pqs > 0.6:
        parts.append("Price perception: positive")
    elif pqs < 0.4:
        parts.append("Price perception: negative")
    else:
        parts.append("Price perception: neutral")

    if resale_ratio is not None:
        parts.append(f"Resale premium: {resale_ratio:.0%}")
    else:
        parts.append("Resale: no data")

    return "; ".join(parts)
