"""Dimension 4 — Brand Health Indicators (BHI).

The "deep layer" of the Sentiment Iceberg.
Measures structural loyalty and brand strength that isn't visible
from surface-level ratings alone.

Components:
    1. NPS Proxy (50%) — Net Promoter Score derived from review text
    2. Response Quality (25%) — Whether the brand engages with customers
    3. Loyalty Signals (25%) — Repeat customer / loyalty language
"""

from __future__ import annotations

from config.settings import (
    BHI_WEIGHTS,
    NPS_PROMOTER_PHRASES,
    NPS_DETRACTOR_PHRASES,
)
from src.analysis.nlp_utils import count_promoter_signals, count_detractor_signals
from src.models.review import ReviewCollection
from src.models.score import BrandHealthScore


def calculate_brand_health(
    collection: ReviewCollection,
) -> BrandHealthScore:
    """Calculate the Brand Health Score from review text signals."""
    components: dict[str, float] = {}

    # ---- 1. NPS Proxy ----
    components["nps_proxy"] = _nps_proxy(collection)

    # ---- 2. Response Quality ----
    components["response_quality"] = _response_quality(collection)

    # ---- 3. Loyalty Signals ----
    components["loyalty_signals"] = _loyalty_signals(collection)

    # Weighted sum → 0–100
    value = sum(
        components[k] * BHI_WEIGHTS[k] * 100
        for k in BHI_WEIGHTS
    )

    explanation = _build_explanation(components, collection)

    return BrandHealthScore(
        value=value,
        components=components,
        explanation=explanation,
    )


def _nps_proxy(collection: ReviewCollection) -> float:
    """Derive a Net Promoter Score proxy from review text.

    NPS = % Promoters - % Detractors (mapped to [0, 1])

    We scan review text for promoter and detractor phrases.
    A review with promoter language = promoter.
    A review with detractor language = detractor.
    A review with neither = passive.
    """
    if not collection.reviews:
        return 0.5

    promoters = 0
    detractors = 0
    passives = 0

    for review in collection.reviews:
        p_count = count_promoter_signals(review.text, NPS_PROMOTER_PHRASES)
        d_count = count_detractor_signals(review.text, NPS_DETRACTOR_PHRASES)

        if p_count > d_count:
            promoters += 1
        elif d_count > p_count:
            detractors += 1
        else:
            passives += 1

    total = promoters + detractors + passives
    if total == 0:
        return 0.5

    # NPS ranges from -100 to +100
    nps_raw = ((promoters - detractors) / total) * 100

    # Map NPS (-100 to +100) to [0, 1]
    return max(0.0, min(1.0, (nps_raw + 100) / 200))


def _response_quality(collection: ReviewCollection) -> float:
    """Score based on whether the brand actively responds to reviews.

    In many review platforms, brand responses show up as replies.
    We detect response-like patterns in the collection.

    Since we're working with public data (not platform APIs with
    explicit response tracking), we use heuristics:
    - Look for reviews from brand-official-sounding authors
    - Look for "thank you for your feedback" style language
    """
    if not collection.reviews:
        return 0.5

    response_indicators = [
        "thank you for your feedback",
        "thank you for your review",
        "we appreciate your feedback",
        "we're sorry to hear",
        "please contact us",
        "our team will",
        "we apologize",
        "we value your",
        "hi, thank you",
    ]

    response_count = 0
    for review in collection.reviews:
        lower_text = review.text.lower()
        if any(indicator in lower_text for indicator in response_indicators):
            response_count += 1

    response_rate = response_count / len(collection.reviews)

    # A 10%+ response rate is excellent for a brand
    if response_rate >= 0.10:
        return 1.0
    elif response_rate >= 0.05:
        return 0.8
    elif response_rate >= 0.02:
        return 0.6
    elif response_rate > 0:
        return 0.4
    else:
        return 0.3  # No responses detected (common for news/social data)


def _loyalty_signals(collection: ReviewCollection) -> float:
    """Detect repeat customer and loyalty language in reviews.

    Loyalty phrases indicate deep brand attachment:
    - "been using for years"
    - "loyal customer"
    - "switched from X to this"
    - "will never use anything else"
    """
    loyalty_phrases = [
        "for years", "for months", "loyal", "long time",
        "switched to", "switched from", "always buy", "always use",
        "never switch", "never use anything else", "my favorite",
        "go-to brand", "go to brand", "repeat customer", "bought again",
        "second time", "third time", "keep coming back",
    ]

    if not collection.reviews:
        return 0.5

    loyalty_count = 0
    for review in collection.reviews:
        lower_text = review.text.lower()
        if any(phrase in lower_text for phrase in loyalty_phrases):
            loyalty_count += 1

    loyalty_rate = loyalty_count / len(collection.reviews)

    # 5%+ loyalty language is strong
    if loyalty_rate >= 0.05:
        return min(1.0, 0.7 + loyalty_rate * 3)
    elif loyalty_rate >= 0.02:
        return 0.6
    elif loyalty_rate > 0:
        return 0.5
    else:
        return 0.4  # No loyalty signals (common for news data)


def _build_explanation(components: dict[str, float], collection: ReviewCollection) -> str:
    parts: list[str] = []

    nps = components["nps_proxy"]
    nps_raw = (nps * 200) - 100
    if nps_raw > 30:
        parts.append(f"NPS proxy: +{nps_raw:.0f} (excellent)")
    elif nps_raw > 0:
        parts.append(f"NPS proxy: +{nps_raw:.0f} (good)")
    elif nps_raw > -30:
        parts.append(f"NPS proxy: {nps_raw:.0f} (needs improvement)")
    else:
        parts.append(f"NPS proxy: {nps_raw:.0f} (critical)")

    rq = components["response_quality"]
    if rq >= 0.8:
        parts.append("Brand engagement: active")
    elif rq >= 0.5:
        parts.append("Brand engagement: moderate")
    else:
        parts.append("Brand engagement: minimal")

    ls = components["loyalty_signals"]
    if ls >= 0.7:
        parts.append("Loyalty: strong signals")
    elif ls >= 0.5:
        parts.append("Loyalty: moderate signals")
    else:
        parts.append("Loyalty: weak signals")

    return "; ".join(parts)
