"""Composite Brand Sentiment Score (BSS) calculator.

Combines all five dimensions into the final score using the
"Sentiment Iceberg" model weighted by predictive power.

    BSS = 0.25×RQS + 0.20×SSS + 0.25×MS + 0.15×BHI + 0.15×CPS

The BSS is a 0–100 score where:
    90–100  A+   Exceptional brand sentiment
    80–89   A    Strong positive sentiment
    70–79   B+   Above average
    60–69   B    Average / healthy
    50–59   C    Below average — watch for decline
    40–49   D    Weak — likely declining popularity
    0–39    F    Critical — active brand damage
"""

from __future__ import annotations

import logging
from datetime import datetime

from config.settings import DIMENSION_WEIGHTS
from src.analysis.sentiment import SentimentAnalyzer
from src.collectors.base import BaseCollector
from src.collectors.google_news import GoogleNewsCollector
from src.collectors.google_trends import GoogleTrendsCollector
from src.collectors.reddit_collector import RedditCollector
from src.collectors.wikipedia import WikipediaCollector
from src.collectors.financial import FinancialCollector
from src.models.brand import Brand
from src.models.review import ReviewCollection
from src.models.score import BrandSentimentScore
from src.scoring.brand_health import calculate_brand_health
from src.scoring.competitive import calculate_competitive_position
from src.scoring.momentum import calculate_momentum
from src.scoring.review_quality import calculate_review_quality
from src.scoring.social_sentiment import calculate_social_sentiment

logger = logging.getLogger(__name__)


class BSSCalculator:
    """Orchestrates data collection, sentiment analysis, and scoring.

    This is the main entry point for computing a Brand Sentiment Score.
    It coordinates all collectors, runs NLP analysis, and combines
    the five dimensions into the final composite score.
    """

    def __init__(
        self,
        sentiment_engine: str = "vader",
        collectors: list[BaseCollector] | None = None,
    ) -> None:
        self.analyzer = SentimentAnalyzer(engine=sentiment_engine)
        self.collectors = collectors or [
            GoogleNewsCollector(),
            RedditCollector(),
            GoogleTrendsCollector(),
            WikipediaCollector(),
            FinancialCollector(),
        ]

    def calculate(
        self,
        brand: Brand,
        competitor_brands: list[Brand] | None = None,
    ) -> BrandSentimentScore:
        """Calculate the complete BSS for a brand.

        Args:
            brand: The brand to score.
            competitor_brands: Optional list of competitor Brand objects
                               for the competitive position dimension.

        Returns:
            A fully populated BrandSentimentScore.
        """
        logger.info("Calculating BSS for '%s'...", brand.name)

        # ----------------------------------------------------------
        # Phase 1: Collect data from all sources
        # ----------------------------------------------------------
        all_reviews = ReviewCollection(brand_name=brand.name)
        source_collections: dict[str, ReviewCollection] = {}
        sources_used: list[str] = []

        for collector in self.collectors:
            collection = collector.collect(brand)
            if collection.count > 0:
                all_reviews.reviews.extend(collection.reviews)
                source_collections[collector.name] = collection
                sources_used.append(collector.name)
                logger.info(
                    "  %s: %d items collected", collector.name, collection.count
                )

        # ----------------------------------------------------------
        # Phase 2: Run sentiment analysis on all collected text
        # ----------------------------------------------------------
        self.analyzer.analyze_collection(all_reviews)

        # Re-sync sentiment scores into source-specific collections
        review_map = {id(r): r for r in all_reviews.reviews}
        for name, coll in source_collections.items():
            for r in coll.reviews:
                analyzed = review_map.get(id(r))
                if analyzed:
                    r.sentiment_compound = analyzed.sentiment_compound
                    r.sentiment_label = analyzed.sentiment_label

        # ----------------------------------------------------------
        # Phase 3: Calculate each dimension
        # ----------------------------------------------------------

        # Dim 1: Review Quality (uses all reviews with ratings)
        rqs = calculate_review_quality(all_reviews)

        # Dim 2: Social Sentiment (split by source type)
        reddit_data = source_collections.get("reddit", ReviewCollection(brand_name=brand.name))
        news_data = source_collections.get("google_news", ReviewCollection(brand_name=brand.name))
        trends_data = source_collections.get("google_trends", ReviewCollection(brand_name=brand.name))
        sss = calculate_social_sentiment(reddit_data, news_data, trends_data)

        # Dim 3: Momentum (uses all time-stamped data)
        ms = calculate_momentum(all_reviews)

        # Dim 4: Brand Health (uses text-heavy reviews)
        bhi = calculate_brand_health(all_reviews)

        # Dim 5: Competitive Position
        competitor_collections: dict[str, ReviewCollection] = {}
        if competitor_brands:
            for comp_brand in competitor_brands:
                comp_reviews = ReviewCollection(brand_name=comp_brand.name)
                for collector in self.collectors:
                    comp_data = collector.collect(comp_brand)
                    if comp_data.count > 0:
                        comp_reviews.reviews.extend(comp_data.reviews)
                self.analyzer.analyze_collection(comp_reviews)
                competitor_collections[comp_brand.name] = comp_reviews
        cps = calculate_competitive_position(all_reviews, competitor_collections)

        # ----------------------------------------------------------
        # Phase 4: Compute composite BSS
        # ----------------------------------------------------------
        bss_value = (
            DIMENSION_WEIGHTS["review_quality"] * rqs.value
            + DIMENSION_WEIGHTS["social_sentiment"] * sss.value
            + DIMENSION_WEIGHTS["momentum"] * ms.value
            + DIMENSION_WEIGHTS["brand_health"] * bhi.value
            + DIMENSION_WEIGHTS["competitive_position"] * cps.value
        )

        # ----------------------------------------------------------
        # Phase 5: Compute confidence
        # ----------------------------------------------------------
        confidence = _compute_confidence(all_reviews, source_collections)

        result = BrandSentimentScore(
            brand_name=brand.name,
            timestamp=datetime.utcnow(),
            bss=bss_value,
            review_quality=rqs,
            social_sentiment=sss,
            momentum=ms,
            brand_health=bhi,
            competitive_position=cps,
            data_sources_used=sources_used,
            total_data_points=all_reviews.count,
            confidence=confidence,
        )

        logger.info(
            "BSS for '%s': %.1f (%s) — confidence: %.0f%%",
            brand.name, result.bss, result.grade(), confidence * 100,
        )

        return result


def _compute_confidence(
    all_reviews: ReviewCollection,
    source_collections: dict[str, ReviewCollection],
) -> float:
    """Confidence score based on data coverage and volume.

    Factors:
    1. Number of active data sources (out of 5 possible)
    2. Total data volume (more data = higher confidence)
    3. Temporal coverage (data spanning more days = better)
    """
    # Source coverage: 5 collectors maximum
    source_score = min(1.0, len(source_collections) / 3)  # 3+ sources = full credit

    # Volume: 50+ data points = full credit
    volume_score = min(1.0, all_reviews.count / 50)

    # Temporal coverage: reviews spanning 30+ days = full credit
    if all_reviews.count >= 2:
        dates = sorted(r.timestamp for r in all_reviews.reviews)
        span_days = (dates[-1] - dates[0]).days
        temporal_score = min(1.0, span_days / 30)
    else:
        temporal_score = 0.0

    return (source_score * 0.4 + volume_score * 0.3 + temporal_score * 0.3)
