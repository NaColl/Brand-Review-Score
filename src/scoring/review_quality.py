"""Dimension 1 — Review Quality Score (RQS).

The "surface layer" of the Sentiment Iceberg.
Measures what customers explicitly say through reviews.

Components:
    1. Normalized Rating (40%) — Time-decay weighted star average
    2. Review Volume Health (25%) — Volume relative to baseline + growth
    3. Review Depth (20%) — Average review length and detail
    4. Sentiment Distribution (15%) — Shape of the rating distribution
"""

from __future__ import annotations

import math
from datetime import datetime

import numpy as np

from config.settings import RQS_WEIGHTS, RECENCY_DECAY_LAMBDA
from src.models.review import ReviewCollection
from src.models.score import ReviewQualityScore


def calculate_review_quality(
    collection: ReviewCollection,
    category_median_volume: int = 100,
) -> ReviewQualityScore:
    """Calculate the Review Quality Score for a brand's review collection."""
    components: dict[str, float] = {}

    # ---- 1. Normalized Rating (time-decay weighted) ----
    components["normalized_rating"] = _normalized_rating(collection)

    # ---- 2. Review Volume Health ----
    components["review_volume_health"] = _volume_health(collection, category_median_volume)

    # ---- 3. Review Depth ----
    components["review_depth"] = _review_depth(collection)

    # ---- 4. Sentiment Distribution ----
    components["sentiment_distribution"] = _sentiment_distribution(collection)

    # Weighted sum → 0–100
    value = sum(
        components[k] * RQS_WEIGHTS[k] * 100
        for k in RQS_WEIGHTS
    )

    explanation = _build_explanation(components, collection)

    return ReviewQualityScore(
        value=value,
        components=components,
        explanation=explanation,
    )


def _normalized_rating(collection: ReviewCollection) -> float:
    """Time-decay weighted average of star ratings, mapped to [0, 1]."""
    rated = [(r.rating, r.timestamp) for r in collection.reviews if r.rating is not None]
    if not rated:
        return 0.5  # Neutral default

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

    # Assuming 1–5 scale, map to [0, 1]
    avg = weighted_sum / weight_total
    return max(0.0, min(1.0, (avg - 1.0) / 4.0))


def _volume_health(collection: ReviewCollection, category_median: int) -> float:
    """Review volume relative to category median, with growth bonus.

    Score = min(1, volume / category_median) × growth_factor
    where growth_factor = 1 + clip(recent_vs_older_ratio - 1, -0.3, 0.3)
    """
    total = collection.count
    if total == 0 or category_median == 0:
        return 0.0

    volume_ratio = min(1.0, total / category_median)

    # Growth: compare recent half to older half
    sorted_reviews = sorted(collection.reviews, key=lambda r: r.timestamp)
    mid = len(sorted_reviews) // 2
    older_count = max(1, mid)
    recent_count = max(1, len(sorted_reviews) - mid)

    growth_ratio = recent_count / older_count
    growth_factor = 1.0 + max(-0.3, min(0.3, growth_ratio - 1.0))

    return min(1.0, volume_ratio * growth_factor)


def _review_depth(collection: ReviewCollection, target_words: int = 50) -> float:
    """Average review word count, mapped through a sigmoid to [0, 1].

    Reviews with ~50+ words get a score near 1.0.
    Very short reviews (< 10 words) get a low score.
    """
    if not collection.reviews:
        return 0.0

    avg_wc = collection.average_word_count
    # Sigmoid: 1 / (1 + exp(-k * (x - midpoint)))
    return 1.0 / (1.0 + math.exp(-0.1 * (avg_wc - target_words)))


def _sentiment_distribution(collection: ReviewCollection) -> float:
    """Score based on the shape of the sentiment distribution.

    A concentrated distribution (mostly positive) scores high.
    A bimodal distribution (love/hate) scores lower.
    Uses normalized entropy: lower entropy = more concentrated = higher score.
    """
    scored = [r.sentiment_compound for r in collection.reviews if r.sentiment_compound is not None]
    if len(scored) < 5:
        return 0.5

    # Bin sentiments into 5 buckets: very neg, neg, neutral, pos, very pos
    bins = [0, 0, 0, 0, 0]
    for s in scored:
        if s <= -0.5:
            bins[0] += 1
        elif s <= -0.05:
            bins[1] += 1
        elif s <= 0.05:
            bins[2] += 1
        elif s <= 0.5:
            bins[3] += 1
        else:
            bins[4] += 1

    total = sum(bins)
    if total == 0:
        return 0.5

    # Normalize to probabilities
    probs = np.array([b / total for b in bins], dtype=float)
    probs = probs[probs > 0]  # Remove zeros for log

    # Shannon entropy
    entropy = -np.sum(probs * np.log2(probs))
    max_entropy = np.log2(5)  # Maximum for 5 bins

    # Lower entropy → more concentrated → higher score
    normalized = 1.0 - (entropy / max_entropy) if max_entropy > 0 else 0.5

    # Bonus: shift up if sentiment is concentrated in positive bins
    positive_mass = sum(bins[3:]) / total
    if positive_mass > 0.6:
        normalized = min(1.0, normalized + 0.1)

    return normalized


def _build_explanation(components: dict[str, float], collection: ReviewCollection) -> str:
    parts: list[str] = []
    nr = components["normalized_rating"]
    star_equiv = 1.0 + nr * 4.0
    parts.append(f"Avg rating: {star_equiv:.1f}/5 (recency-weighted)")
    parts.append(f"Volume: {collection.count} reviews")
    parts.append(f"Avg depth: {collection.average_word_count:.0f} words/review")

    sd = components["sentiment_distribution"]
    if sd > 0.7:
        parts.append("Sentiment: concentrated (consistent)")
    elif sd < 0.4:
        parts.append("Sentiment: dispersed (polarized)")
    else:
        parts.append("Sentiment: moderate spread")

    return "; ".join(parts)
