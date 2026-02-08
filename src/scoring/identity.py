"""Dimension 2 — Identity Score.

Do people understand and align with the brand's values?

Components:
    1. Narrative Sentiment (35%) — Tone of earned media narratives
    2. Values Alignment (35%) — How often brand values appear in discussion
    3. Consistency (30%) — Is sentiment stable over time? (low variance = consistent)
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from config.settings import IDENT_WEIGHTS, BRAND_VALUES_KEYWORDS
from src.models.review import ReviewCollection
from src.models.score import IdentityScore


def calculate_identity(
    all_collection: ReviewCollection,
    news_collection: ReviewCollection,
    brand_values: list[str] | None = None,
) -> IdentityScore:
    """Calculate the Identity Score.

    Args:
        all_collection: All collected reviews/mentions with sentiment.
        news_collection: News articles specifically (earned media).
        brand_values: Optional list of value categories the brand claims
                      (e.g., ["sustainability", "craftsmanship"]).
                      If None, all BRAND_VALUES_KEYWORDS categories are checked.
    """
    components: dict[str, float] = {}

    # 1. Narrative Sentiment — tone of earned media
    components["narrative_sentiment"] = _narrative_sentiment(news_collection)

    # 2. Values Alignment — how often brand-relevant value keywords appear
    components["values_alignment"] = _values_alignment(all_collection, brand_values)

    # 3. Consistency — low sentiment variance over time
    components["consistency"] = _consistency(all_collection)

    value = sum(components[k] * IDENT_WEIGHTS[k] * 100 for k in IDENT_WEIGHTS)

    explanation = _build_explanation(components)

    return IdentityScore(
        value=value,
        components=components,
        explanation=explanation,
    )


def _narrative_sentiment(news: ReviewCollection) -> float:
    scored = [r.sentiment_compound for r in news.reviews if r.sentiment_compound is not None]
    if not scored:
        return 0.5
    avg = sum(scored) / len(scored)
    return max(0.0, min(1.0, (avg + 1.0) / 2.0))


def _values_alignment(collection: ReviewCollection, brand_values: list[str] | None) -> float:
    if not collection.reviews:
        return 0.5

    categories = brand_values or list(BRAND_VALUES_KEYWORDS.keys())
    total_mentions = 0
    total_reviews = len(collection.reviews)

    for review in collection.reviews:
        lower_text = review.text.lower()
        for category in categories:
            keywords = BRAND_VALUES_KEYWORDS.get(category, [])
            if any(kw in lower_text for kw in keywords):
                total_mentions += 1
                break  # Count each review only once

    mention_rate = total_mentions / total_reviews
    # 10%+ mention rate of values = strong alignment
    if mention_rate >= 0.10:
        return min(1.0, 0.7 + mention_rate)
    elif mention_rate >= 0.05:
        return 0.6
    elif mention_rate > 0:
        return 0.4
    return 0.3


def _consistency(collection: ReviewCollection) -> float:
    """Low sentiment variance over time = consistent brand identity."""
    scored = [r.sentiment_compound for r in collection.reviews if r.sentiment_compound is not None]
    if len(scored) < 5:
        return 0.5

    arr = np.array(scored)
    std = float(np.std(arr))
    # Low std = consistent. std of 0.1 = very consistent, 0.5 = very inconsistent
    if std <= 0.15:
        return 0.9
    elif std <= 0.25:
        return 0.7
    elif std <= 0.35:
        return 0.5
    elif std <= 0.50:
        return 0.3
    return 0.1


def _build_explanation(components: dict[str, float]) -> str:
    parts = []
    ns = components["narrative_sentiment"]
    parts.append(f"Media narrative: {'positive' if ns > 0.6 else 'negative' if ns < 0.4 else 'neutral'}")
    va = components["values_alignment"]
    parts.append(f"Values alignment: {'strong' if va > 0.6 else 'weak' if va < 0.4 else 'moderate'}")
    c = components["consistency"]
    parts.append(f"Messaging: {'consistent' if c > 0.6 else 'inconsistent' if c < 0.4 else 'variable'}")
    return "; ".join(parts)
