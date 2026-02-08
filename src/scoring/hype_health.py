"""Hype vs Health Index (HHI) — Separate top-level metric.

A 2-axis metric that separates buzz from substance:

    HYPE AXIS (0-100):
    - Google Trends search interest
    - Social media mention volume
    - Wikipedia pageview level
    - News coverage volume

    HEALTH AXIS (0-100):
    - Stock price momentum (public companies)
    - Financial fundamentals signals
    - Low sale percentage (demand strength)
    - Resale premium (brand equity retention)

    QUADRANTS:
    ┌─────────────────┬─────────────────┐
    │   OVERHYPED     │  STRONG BRAND   │
    │  High Hype      │  High Hype      │
    │  Low Health      │  High Health    │
    │  (bubble risk)   │  (ideal state)  │
    ├─────────────────┼─────────────────┤
    │   DECLINING     │  HIDDEN GEM     │
    │  Low Hype       │  Low Hype       │
    │  Low Health      │  High Health    │
    │  (avoid)         │  (undervalued)  │
    └─────────────────┴─────────────────┘
"""

from __future__ import annotations

from datetime import datetime

from config.settings import HHI_WEIGHTS
from src.models.review import ReviewCollection
from src.models.score import HypeHealthIndex


def calculate_hype_health(
    trends_collection: ReviewCollection,
    reddit_collection: ReviewCollection,
    news_collection: ReviewCollection,
    wiki_collection: ReviewCollection,
    stock_momentum: float | None = None,
    revenue_growth: float | None = None,
    sale_percentage: float | None = None,
    resale_premium_ratio: float | None = None,
) -> HypeHealthIndex:
    """Calculate the Hype vs Health Index.

    Args:
        trends_collection: Google Trends data.
        reddit_collection: Reddit mentions.
        news_collection: News articles.
        wiki_collection: Wikipedia pageview data.
        stock_momentum: Stock price change % over 30 days (public companies).
        revenue_growth: Revenue growth rate (if available).
        sale_percentage: % of products on sale.
        resale_premium_ratio: Resale price / retail price.
    """
    # --- HYPE SCORE ---
    hype_components: dict[str, float] = {}

    # Google Trends (0-100 raw → 0-1)
    trends_interests = [r.engagement for r in trends_collection.reviews if r.engagement > 0]
    if trends_interests:
        hype_components["google_trends"] = min(1.0, sum(trends_interests) / len(trends_interests) / 100)
    else:
        hype_components["google_trends"] = 0.0

    # Social volume
    if reddit_collection.count > 0:
        social_vol = min(1.0, reddit_collection.count / 100)
    else:
        social_vol = 0.0
    hype_components["social_volume"] = social_vol

    # Wikipedia pageviews
    wiki_views = [r.engagement for r in wiki_collection.reviews if r.engagement > 0]
    if wiki_views:
        avg_views = sum(wiki_views) / len(wiki_views)
        hype_components["wikipedia_pageviews"] = min(1.0, avg_views / 10000)
    else:
        hype_components["wikipedia_pageviews"] = 0.0

    # News volume
    hype_components["news_volume"] = min(1.0, news_collection.count / 30)

    hype_score = sum(
        hype_components[k] * HHI_WEIGHTS["hype"][k] * 100
        for k in HHI_WEIGHTS["hype"]
    )

    # --- HEALTH SCORE ---
    health_components: dict[str, float] = {}

    # Stock momentum
    if stock_momentum is not None:
        if stock_momentum >= 10:
            health_components["stock_momentum"] = 1.0
        elif stock_momentum >= 0:
            health_components["stock_momentum"] = 0.5 + stock_momentum / 20
        elif stock_momentum >= -10:
            health_components["stock_momentum"] = 0.5 + stock_momentum / 20
        else:
            health_components["stock_momentum"] = max(0.0, 0.5 + stock_momentum / 40)
    else:
        health_components["stock_momentum"] = 0.5

    # Financial fundamentals
    if revenue_growth is not None:
        health_components["financials"] = min(1.0, max(0.0, 0.5 + revenue_growth))
    else:
        health_components["financials"] = 0.5

    # Low sale % = healthy demand (invert: lower sale % → higher score)
    if sale_percentage is not None:
        health_components["low_sale_pct"] = max(0.0, 1.0 - sale_percentage * 2)
    else:
        health_components["low_sale_pct"] = 0.5

    # Resale premium
    if resale_premium_ratio is not None:
        if resale_premium_ratio >= 1.0:
            health_components["resale_premium"] = min(1.0, resale_premium_ratio)
        else:
            health_components["resale_premium"] = resale_premium_ratio
    else:
        health_components["resale_premium"] = 0.5

    health_score = sum(
        health_components[k] * HHI_WEIGHTS["health"][k] * 100
        for k in HHI_WEIGHTS["health"]
    )

    return HypeHealthIndex(
        brand_name=trends_collection.brand_name or news_collection.brand_name,
        timestamp=datetime.utcnow(),
        hype_score=hype_score,
        health_score=health_score,
        hype_components=hype_components,
        health_components=health_components,
    )
