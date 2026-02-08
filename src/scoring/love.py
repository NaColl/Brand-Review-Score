"""Dimension 5 — Love Score.

Do people feel emotionally attached and advocate for the brand?

Components:
    1. NPS Proxy (35%) — Net Promoter Score from review text
    2. Loyalty Signals (25%) — Repeat customer / long-term user language
    3. Advocacy Intensity (25%) — Strength of positive recommendations
    4. Emotional Attachment (15%) — "obsessed", "can't live without" language
"""

from __future__ import annotations

from config.settings import (
    LOVE_WEIGHTS,
    NPS_PROMOTER_PHRASES,
    NPS_DETRACTOR_PHRASES,
    EMOTIONAL_ATTACHMENT_PHRASES,
)
from src.analysis.nlp_utils import count_promoter_signals, count_detractor_signals
from src.models.review import ReviewCollection
from src.models.score import LoveScore


def calculate_love(
    collection: ReviewCollection,
) -> LoveScore:
    """Calculate the Love Score from text-based loyalty signals."""
    components: dict[str, float] = {}

    components["nps_proxy"] = _nps_proxy(collection)
    components["loyalty_signals"] = _loyalty_signals(collection)
    components["advocacy_intensity"] = _advocacy_intensity(collection)
    components["emotional_attachment"] = _emotional_attachment(collection)

    value = sum(components[k] * LOVE_WEIGHTS[k] * 100 for k in LOVE_WEIGHTS)

    explanation = _build_explanation(components)

    return LoveScore(
        value=value,
        components=components,
        explanation=explanation,
    )


def _nps_proxy(collection: ReviewCollection) -> float:
    if not collection.reviews:
        return 0.5
    promoters = 0
    detractors = 0
    for review in collection.reviews:
        p = count_promoter_signals(review.text, NPS_PROMOTER_PHRASES)
        d = count_detractor_signals(review.text, NPS_DETRACTOR_PHRASES)
        if p > d:
            promoters += 1
        elif d > p:
            detractors += 1
    total = len(collection.reviews)
    nps_raw = ((promoters - detractors) / total) * 100
    return max(0.0, min(1.0, (nps_raw + 100) / 200))


def _loyalty_signals(collection: ReviewCollection) -> float:
    loyalty_phrases = [
        "for years", "for months", "loyal", "long time",
        "switched to", "switched from", "always buy", "always use",
        "never switch", "never use anything else", "my favorite",
        "go-to brand", "go to brand", "repeat customer", "bought again",
        "second time", "third time", "keep coming back",
    ]
    if not collection.reviews:
        return 0.5
    count = 0
    for review in collection.reviews:
        lower = review.text.lower()
        if any(phrase in lower for phrase in loyalty_phrases):
            count += 1
    rate = count / len(collection.reviews)
    if rate >= 0.05:
        return min(1.0, 0.7 + rate * 3)
    elif rate >= 0.02:
        return 0.6
    elif rate > 0:
        return 0.5
    return 0.4


def _advocacy_intensity(collection: ReviewCollection) -> float:
    """How strongly do promoters advocate?

    Measures the sentiment intensity of reviews containing promoter language.
    Strong advocacy = high compound score + promoter phrases.
    """
    if not collection.reviews:
        return 0.5

    advocacy_scores = []
    for review in collection.reviews:
        if review.sentiment_compound is not None:
            p_count = count_promoter_signals(review.text, NPS_PROMOTER_PHRASES)
            if p_count > 0:
                advocacy_scores.append(review.sentiment_compound)

    if not advocacy_scores:
        return 0.5

    avg_intensity = sum(advocacy_scores) / len(advocacy_scores)
    # Map from typically [0, 1] to [0, 1]
    return max(0.0, min(1.0, avg_intensity))


def _emotional_attachment(collection: ReviewCollection) -> float:
    """Presence of deep emotional attachment language."""
    if not collection.reviews:
        return 0.5

    count = 0
    for review in collection.reviews:
        lower = review.text.lower()
        if any(phrase in lower for phrase in EMOTIONAL_ATTACHMENT_PHRASES):
            count += 1

    rate = count / len(collection.reviews)
    # Even 2% emotional attachment language is significant
    if rate >= 0.05:
        return 1.0
    elif rate >= 0.02:
        return 0.8
    elif rate > 0:
        return 0.6
    return 0.3


def _build_explanation(components: dict[str, float]) -> str:
    parts = []
    nps = components["nps_proxy"]
    nps_raw = (nps * 200) - 100
    parts.append(f"NPS proxy: {nps_raw:+.0f}")
    ls = components["loyalty_signals"]
    parts.append(f"Loyalty: {'strong' if ls > 0.6 else 'weak' if ls < 0.4 else 'moderate'}")
    ea = components["emotional_attachment"]
    parts.append(f"Attachment: {'deep' if ea > 0.6 else 'minimal' if ea < 0.4 else 'moderate'}")
    return "; ".join(parts)
