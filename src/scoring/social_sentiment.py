"""Dimension 2 — Social Sentiment Score (SSS).

The "current layer" of the Sentiment Iceberg.
Measures the direction and tone of broader social conversation.

Components:
    1. Reddit Sentiment (40%) — Discussion tone in relevant subreddits
    2. News Sentiment (40%) — Google News headline sentiment
    3. Search Interest (20%) — Google Trends normalized interest
"""

from __future__ import annotations

from config.settings import SSS_WEIGHTS, NEGATIVITY_BIAS_MULTIPLIER
from src.models.review import ReviewCollection
from src.models.score import SocialSentimentScore


def calculate_social_sentiment(
    reddit_collection: ReviewCollection,
    news_collection: ReviewCollection,
    trends_collection: ReviewCollection,
) -> SocialSentimentScore:
    """Calculate the Social Sentiment Score from social/news/search data."""
    components: dict[str, float] = {}

    # ---- 1. Reddit Sentiment ----
    components["reddit_sentiment"] = _engagement_weighted_sentiment(reddit_collection)

    # ---- 2. News Sentiment ----
    components["news_sentiment"] = _average_sentiment(news_collection)

    # ---- 3. Search Interest ----
    components["search_interest"] = _search_interest_score(trends_collection)

    # Weighted sum → 0–100
    value = sum(
        components[k] * SSS_WEIGHTS[k] * 100
        for k in SSS_WEIGHTS
    )

    explanation = _build_explanation(components, reddit_collection, news_collection)

    return SocialSentimentScore(
        value=value,
        components=components,
        explanation=explanation,
    )


def _engagement_weighted_sentiment(collection: ReviewCollection) -> float:
    """Sentiment weighted by engagement (upvotes/score).

    Highly-upvoted posts reflect the community's true sentiment better
    than low-engagement posts. Applies negativity bias multiplier.
    """
    scored = [
        (r.sentiment_compound, max(1, r.engagement))
        for r in collection.reviews
        if r.sentiment_compound is not None
    ]
    if not scored:
        return 0.5

    weighted_sum = 0.0
    weight_total = 0.0

    for sentiment, engagement in scored:
        # Apply negativity bias: negative sentiment gets amplified
        if sentiment < 0:
            adjusted = sentiment * NEGATIVITY_BIAS_MULTIPLIER
        else:
            adjusted = sentiment

        weighted_sum += adjusted * engagement
        weight_total += engagement

    if weight_total == 0:
        return 0.5

    # Raw weighted average is in [-1, 1] (or wider due to negativity bias)
    # Map to [0, 1]
    raw = weighted_sum / weight_total
    return max(0.0, min(1.0, (raw + 1.0) / 2.0))


def _average_sentiment(collection: ReviewCollection) -> float:
    """Simple average sentiment mapped to [0, 1] with negativity bias."""
    scored = [r.sentiment_compound for r in collection.reviews if r.sentiment_compound is not None]
    if not scored:
        return 0.5

    # Apply negativity bias
    adjusted = []
    for s in scored:
        if s < 0:
            adjusted.append(s * NEGATIVITY_BIAS_MULTIPLIER)
        else:
            adjusted.append(s)

    avg = sum(adjusted) / len(adjusted)
    return max(0.0, min(1.0, (avg + 1.0) / 2.0))


def _search_interest_score(trends_collection: ReviewCollection) -> float:
    """Map Google Trends engagement (interest 0-100) to [0, 1].

    Higher search interest = more brand awareness.
    We look at the trend level and its trajectory.
    """
    if not trends_collection.reviews:
        return 0.5  # Neutral if unavailable

    # engagement field stores the raw interest value (0-100)
    interests = [r.engagement for r in trends_collection.reviews]
    if not interests:
        return 0.5

    # Average interest level
    avg_interest = sum(interests) / len(interests)

    # Recent vs older (trend direction)
    mid = len(interests) // 2
    if mid > 0:
        older_avg = sum(interests[:mid]) / mid
        recent_avg = sum(interests[mid:]) / max(1, len(interests) - mid)
        if older_avg > 0:
            trend_factor = min(1.3, max(0.7, recent_avg / older_avg))
        else:
            trend_factor = 1.0
    else:
        trend_factor = 1.0

    # Map to [0, 1]: 50/100 interest = baseline 0.5
    base = avg_interest / 100.0
    return max(0.0, min(1.0, base * trend_factor))


def _build_explanation(
    components: dict[str, float],
    reddit: ReviewCollection,
    news: ReviewCollection,
) -> str:
    parts: list[str] = []

    reddit_s = components["reddit_sentiment"]
    if reddit.count > 0:
        label = "positive" if reddit_s > 0.6 else "negative" if reddit_s < 0.4 else "neutral"
        parts.append(f"Reddit: {label} ({reddit.count} posts/comments)")
    else:
        parts.append("Reddit: no data")

    news_s = components["news_sentiment"]
    if news.count > 0:
        label = "positive" if news_s > 0.6 else "negative" if news_s < 0.4 else "neutral"
        parts.append(f"News: {label} ({news.count} articles)")
    else:
        parts.append("News: no data")

    search = components["search_interest"]
    level = "high" if search > 0.7 else "low" if search < 0.3 else "moderate"
    parts.append(f"Search interest: {level}")

    return "; ".join(parts)
