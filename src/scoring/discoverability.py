"""Dimension 1 — Discoverability Score.

How easily can people find the brand via search, social, and news?

Components:
    1. Search Volume (30%) — Google Trends absolute interest level
    2. Search Trend (20%) — Is search interest rising or falling?
    3. News Volume (20%) — Number of recent news articles
    4. Social Reach (15%) — Reddit mention volume + engagement
    5. Wikipedia Interest (15%) — Pageview level as awareness proxy
"""

from __future__ import annotations

from datetime import datetime, timedelta

from config.settings import DISC_WEIGHTS
from src.models.review import ReviewCollection
from src.models.score import DiscoverabilityScore


def calculate_discoverability(
    news_collection: ReviewCollection,
    reddit_collection: ReviewCollection,
    trends_collection: ReviewCollection,
    wiki_collection: ReviewCollection,
) -> DiscoverabilityScore:
    """Calculate the Discoverability Score from multi-source volume data."""
    components: dict[str, float] = {}

    # 1. Search Volume — average Google Trends interest (0-100 mapped to 0-1)
    components["search_volume"] = _search_volume(trends_collection)

    # 2. Search Trend — is interest rising or falling?
    components["search_trend"] = _search_trend(trends_collection)

    # 3. News Volume — how many articles were published?
    components["news_volume"] = _news_volume(news_collection)

    # 4. Social Reach — Reddit mentions weighted by engagement
    components["social_reach"] = _social_reach(reddit_collection)

    # 5. Wikipedia Interest — pageview level
    components["wikipedia_interest"] = _wikipedia_interest(wiki_collection)

    value = sum(components[k] * DISC_WEIGHTS[k] * 100 for k in DISC_WEIGHTS)

    explanation = _build_explanation(components, news_collection, reddit_collection)

    return DiscoverabilityScore(
        value=value,
        components=components,
        explanation=explanation,
    )


def _search_volume(trends: ReviewCollection) -> float:
    if not trends.reviews:
        return 0.5
    interests = [r.engagement for r in trends.reviews if r.engagement > 0]
    if not interests:
        return 0.5
    return min(1.0, sum(interests) / len(interests) / 100.0)


def _search_trend(trends: ReviewCollection) -> float:
    if len(trends.reviews) < 4:
        return 0.5
    interests = [r.engagement for r in sorted(trends.reviews, key=lambda r: r.timestamp)]
    mid = len(interests) // 2
    older = sum(interests[:mid]) / max(1, mid)
    recent = sum(interests[mid:]) / max(1, len(interests) - mid)
    if older == 0:
        return 0.7 if recent > 0 else 0.5
    ratio = recent / older
    return max(0.0, min(1.0, 0.3 + ratio * 0.35))


def _news_volume(news: ReviewCollection) -> float:
    count = news.count
    if count >= 40:
        return 1.0
    elif count >= 20:
        return 0.8
    elif count >= 10:
        return 0.6
    elif count >= 5:
        return 0.4
    elif count > 0:
        return 0.2
    return 0.0


def _social_reach(reddit: ReviewCollection) -> float:
    if not reddit.reviews:
        return 0.0
    total_engagement = sum(max(0, r.engagement) for r in reddit.reviews)
    avg_engagement = total_engagement / len(reddit.reviews)
    count_score = min(1.0, reddit.count / 50)
    engagement_score = min(1.0, avg_engagement / 100)
    return count_score * 0.5 + engagement_score * 0.5


def _wikipedia_interest(wiki: ReviewCollection) -> float:
    if not wiki.reviews:
        return 0.0
    pageviews = [r.engagement for r in wiki.reviews if r.engagement > 0]
    if not pageviews:
        return 0.0
    avg = sum(pageviews) / len(pageviews)
    # 10K daily pageviews = strong, 1K = moderate, <100 = weak
    if avg >= 10000:
        return 1.0
    elif avg >= 1000:
        return 0.6 + (avg - 1000) / 9000 * 0.4
    elif avg >= 100:
        return 0.2 + (avg - 100) / 900 * 0.4
    else:
        return avg / 100 * 0.2


def _build_explanation(
    components: dict[str, float],
    news: ReviewCollection,
    reddit: ReviewCollection,
) -> str:
    parts = []
    sv = components["search_volume"]
    level = "high" if sv > 0.7 else "low" if sv < 0.3 else "moderate"
    parts.append(f"Search: {level}")

    st = components["search_trend"]
    direction = "rising" if st > 0.6 else "falling" if st < 0.4 else "stable"
    parts.append(f"Trend: {direction}")

    parts.append(f"News: {news.count} articles")
    parts.append(f"Social: {reddit.count} mentions")

    return "; ".join(parts)
