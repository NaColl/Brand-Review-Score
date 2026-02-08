"""Dimension 4 — Connection Score.

Do people engage and resonate emotionally with the brand?

Components:
    1. Engagement Rate (40%) — Upvotes, comments, shares per mention
    2. Emotional Tone (30%) — Intensity of emotional language
    3. Community Growth (30%) — Volume trend of engaged mentions
"""

from __future__ import annotations

from datetime import datetime, timedelta

from config.settings import CONN_WEIGHTS, HIGH_ENGAGEMENT_PHRASES
from src.models.review import ReviewCollection
from src.models.score import ConnectionScore


def calculate_connection(
    collection: ReviewCollection,
) -> ConnectionScore:
    """Calculate the Connection Score from engagement signals."""
    components: dict[str, float] = {}

    # 1. Engagement Rate
    components["engagement_rate"] = _engagement_rate(collection)

    # 2. Emotional Tone
    components["emotional_tone"] = _emotional_tone(collection)

    # 3. Community Growth
    components["community_growth"] = _community_growth(collection)

    value = sum(components[k] * CONN_WEIGHTS[k] * 100 for k in CONN_WEIGHTS)

    explanation = _build_explanation(components, collection)

    return ConnectionScore(
        value=value,
        components=components,
        explanation=explanation,
    )


def _engagement_rate(collection: ReviewCollection) -> float:
    """Average engagement per mention, normalized."""
    if not collection.reviews:
        return 0.0

    engagements = [max(0, r.engagement) for r in collection.reviews]
    if not engagements:
        return 0.0

    avg = sum(engagements) / len(engagements)

    # Engagement thresholds (calibrated for Reddit-like platforms)
    if avg >= 200:
        return 1.0
    elif avg >= 100:
        return 0.8
    elif avg >= 50:
        return 0.65
    elif avg >= 20:
        return 0.5
    elif avg >= 5:
        return 0.35
    elif avg > 0:
        return 0.2
    return 0.1


def _emotional_tone(collection: ReviewCollection) -> float:
    """Intensity of emotional language (both positive and negative).

    High-intensity emotions indicate deeper connection than neutral mentions.
    We measure: |compound sentiment| and presence of high-engagement phrases.
    """
    if not collection.reviews:
        return 0.5

    intensities = []
    phrase_hits = 0

    for review in collection.reviews:
        if review.sentiment_compound is not None:
            intensities.append(abs(review.sentiment_compound))
        lower = review.text.lower()
        if any(phrase in lower for phrase in HIGH_ENGAGEMENT_PHRASES):
            phrase_hits += 1

    avg_intensity = sum(intensities) / len(intensities) if intensities else 0.0
    phrase_rate = phrase_hits / len(collection.reviews)

    # High intensity + engagement phrases = deep emotional connection
    intensity_score = min(1.0, avg_intensity * 1.5)  # Scale up since most text is mild
    phrase_score = min(1.0, phrase_rate * 10)  # 10%+ phrase rate = excellent

    return intensity_score * 0.7 + phrase_score * 0.3


def _community_growth(collection: ReviewCollection) -> float:
    """Is the volume of engaged mentions growing?

    Compares recent 14-day volume to preceding 14-day volume.
    """
    if len(collection.reviews) < 5:
        return 0.5

    now = datetime.utcnow()
    recent_cutoff = now - timedelta(days=14)
    older_cutoff = now - timedelta(days=28)

    recent_count = sum(
        1 for r in collection.reviews
        if r.timestamp >= recent_cutoff
    )
    older_count = sum(
        1 for r in collection.reviews
        if older_cutoff <= r.timestamp < recent_cutoff
    )

    if older_count == 0:
        return 0.6 if recent_count > 0 else 0.5

    growth_ratio = recent_count / older_count

    if growth_ratio >= 1.5:
        return 1.0
    elif growth_ratio >= 1.2:
        return 0.8
    elif growth_ratio >= 0.9:
        return 0.6
    elif growth_ratio >= 0.7:
        return 0.4
    else:
        return 0.2


def _build_explanation(components: dict[str, float], collection: ReviewCollection) -> str:
    parts = []
    er = components["engagement_rate"]
    parts.append(f"Engagement: {'high' if er > 0.6 else 'low' if er < 0.3 else 'moderate'}")
    et = components["emotional_tone"]
    parts.append(f"Emotional intensity: {'strong' if et > 0.6 else 'mild' if et < 0.3 else 'moderate'}")
    cg = components["community_growth"]
    parts.append(f"Community: {'growing' if cg > 0.6 else 'shrinking' if cg < 0.4 else 'stable'}")
    return "; ".join(parts)
