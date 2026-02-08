"""Composite Brand Sentiment Score (BSS) v2 calculator.

Combines 8 unified dimensions + Hype vs Health Index + Luxury Brand Index.

    BSS = Σ(weight_i × dimension_i) for i in 1..8

Supports two weighting profiles:
- DEFAULT: General brand scoring
- LUXURY: Luxury brand scoring (auto-detected or manual)
"""

from __future__ import annotations

import logging
from datetime import datetime

from config.settings import (
    DIMENSION_WEIGHTS,
    LUXURY_DIMENSION_WEIGHTS,
    LUXURY_BRANDS,
    LUXURY_ASPIRATIONAL_PHRASES,
    LUXURY_DEVALUATION_PHRASES,
)
from src.analysis.sentiment import SentimentAnalyzer
from src.collectors.base import BaseCollector
from src.collectors.google_news import GoogleNewsCollector
from src.collectors.google_trends import GoogleTrendsCollector
from src.collectors.reddit_collector import RedditCollector
from src.collectors.wikipedia import WikipediaCollector
from src.collectors.financial import FinancialCollector
from src.collectors.resale import ResaleCollector
from src.models.brand import Brand
from src.models.review import ReviewCollection
from src.models.score import (
    BrandSentimentScore,
    LuxuryBrandIndex,
)
from src.scoring.discoverability import calculate_discoverability
from src.scoring.identity import calculate_identity
from src.scoring.value_perception import calculate_value_perception
from src.scoring.connection import calculate_connection
from src.scoring.love import calculate_love
from src.scoring.momentum import calculate_momentum
from src.scoring.competitive import calculate_competitive_position
from src.scoring.pricing_intelligence import calculate_pricing_intelligence
from src.scoring.hype_health import calculate_hype_health

logger = logging.getLogger(__name__)


class BSSCalculator:
    """Orchestrates data collection, sentiment analysis, and scoring.

    v2: 8 dimensions + HHI + Luxury Brand Index.
    """

    def __init__(
        self,
        sentiment_engine: str = "vader",
        collectors: list[BaseCollector] | None = None,
        force_luxury: bool | None = None,
    ) -> None:
        self.analyzer = SentimentAnalyzer(engine=sentiment_engine)
        self.collectors = collectors or [
            GoogleNewsCollector(),
            RedditCollector(),
            GoogleTrendsCollector(),
            WikipediaCollector(),
            FinancialCollector(),
        ]
        self.resale_collector = ResaleCollector()
        self.force_luxury = force_luxury

    def calculate(
        self,
        brand: Brand,
        competitor_brands: list[Brand] | None = None,
        sale_percentage: float | None = None,
        avg_discount_pct: float | None = None,
        resale_value_ratio: float | None = None,
        demo_data: dict[str, ReviewCollection] | None = None,
        demo_competitors: dict[str, ReviewCollection] | None = None,
    ) -> BrandSentimentScore:
        """Calculate the complete BSS for a brand.

        Args:
            brand: The brand to score.
            competitor_brands: Competitor Brand objects for CPS dimension.
            sale_percentage: % of products on sale (0.0-1.0).
            avg_discount_pct: Average discount % (0.0-1.0).
            resale_value_ratio: Resale/retail price ratio.
            demo_data: Pre-built source collections (skips live collection).
            demo_competitors: Pre-built competitor collections.
        """
        logger.info("Calculating BSS v2 for '%s'...", brand.name)

        # Detect luxury
        is_luxury = self._detect_luxury(brand)

        # ----------------------------------------------------------
        # Phase 1: Collect data from all sources
        # ----------------------------------------------------------
        all_reviews = ReviewCollection(brand_name=brand.name)
        source_collections: dict[str, ReviewCollection] = {}
        sources_used: list[str] = []

        if demo_data:
            # Use pre-built demo data — skip live collection
            for source_name, collection in demo_data.items():
                if collection.count > 0:
                    all_reviews.reviews.extend(collection.reviews)
                    source_collections[source_name] = collection
                    sources_used.append(source_name)
                    logger.info("  %s: %d items (demo)", source_name, collection.count)
        else:
            for collector in self.collectors:
                collection = collector.collect(brand)
                if collection.count > 0:
                    all_reviews.reviews.extend(collection.reviews)
                    source_collections[collector.name] = collection
                    sources_used.append(collector.name)
                    logger.info("  %s: %d items", collector.name, collection.count)

            # Resale data collection (especially for luxury)
            resale_data = self.resale_collector.collect(brand)
            if resale_data.count > 0:
                all_reviews.reviews.extend(resale_data.reviews)
                source_collections["resale"] = resale_data
                sources_used.append("resale")

        # Estimate resale ratio if not provided
        if resale_value_ratio is None and is_luxury:
            if demo_data:
                resale_value_ratio = 0.85  # Reasonable luxury default for demo
            else:
                resale_value_ratio = self.resale_collector.estimate_resale_ratio(brand)

        # ----------------------------------------------------------
        # Phase 2: Run sentiment analysis
        # ----------------------------------------------------------
        self.analyzer.analyze_collection(all_reviews)

        # Sync sentiment into source collections
        review_map = {id(r): r for r in all_reviews.reviews}
        for coll in source_collections.values():
            for r in coll.reviews:
                analyzed = review_map.get(id(r))
                if analyzed:
                    r.sentiment_compound = analyzed.sentiment_compound
                    r.sentiment_label = analyzed.sentiment_label

        # ----------------------------------------------------------
        # Phase 3: Calculate all 8 dimensions
        # ----------------------------------------------------------
        reddit_data = source_collections.get("reddit", ReviewCollection(brand_name=brand.name))
        news_data = source_collections.get("google_news", ReviewCollection(brand_name=brand.name))
        trends_data = source_collections.get("google_trends", ReviewCollection(brand_name=brand.name))
        wiki_data = source_collections.get("wikipedia", ReviewCollection(brand_name=brand.name))

        disc = calculate_discoverability(news_data, reddit_data, trends_data, wiki_data)
        ident = calculate_identity(all_reviews, news_data)
        val = calculate_value_perception(all_reviews, resale_premium_ratio=resale_value_ratio)
        conn = calculate_connection(all_reviews)
        love = calculate_love(all_reviews)
        mom = calculate_momentum(all_reviews)

        # Competitive Position
        competitor_collections: dict[str, ReviewCollection] = {}
        if demo_competitors:
            competitor_collections = demo_competitors
        elif competitor_brands:
            for comp_brand in competitor_brands:
                comp_reviews = ReviewCollection(brand_name=comp_brand.name)
                for collector in self.collectors:
                    comp_data = collector.collect(comp_brand)
                    if comp_data.count > 0:
                        comp_reviews.reviews.extend(comp_data.reviews)
                self.analyzer.analyze_collection(comp_reviews)
                competitor_collections[comp_brand.name] = comp_reviews
        cps = calculate_competitive_position(all_reviews, competitor_collections)

        pricing = calculate_pricing_intelligence(
            all_reviews,
            sale_percentage=sale_percentage,
            avg_discount_pct=avg_discount_pct,
            resale_value_ratio=resale_value_ratio,
        )

        # ----------------------------------------------------------
        # Phase 4: Compute composite BSS
        # ----------------------------------------------------------
        weights = LUXURY_DIMENSION_WEIGHTS if is_luxury else DIMENSION_WEIGHTS

        dimension_map = {
            "discoverability": disc,
            "identity": ident,
            "value_perception": val,
            "connection": conn,
            "love": love,
            "momentum": mom,
            "competitive_position": cps,
            "pricing_intelligence": pricing,
        }

        bss_value = sum(
            weights[dim_name] * dim_score.value
            for dim_name, dim_score in dimension_map.items()
        )

        # ----------------------------------------------------------
        # Phase 5: Hype vs Health Index
        # ----------------------------------------------------------
        stock_momentum = None
        if demo_data and brand.ticker:
            # Use realistic demo stock momentum
            demo_stock = {"Nike": 5.2, "Chanel": None, "Tesla": -3.8, "Gap": -12.4}
            stock_momentum = demo_stock.get(brand.name)
        else:
            financial_collector = next(
                (c for c in self.collectors if isinstance(c, FinancialCollector)), None
            )
            if financial_collector and brand.ticker:
                stock_momentum = financial_collector.get_price_change(brand, days=30)

        hhi = calculate_hype_health(
            trends_collection=trends_data,
            reddit_collection=reddit_data,
            news_collection=news_data,
            wiki_collection=wiki_data,
            stock_momentum=stock_momentum,
            sale_percentage=sale_percentage,
            resale_premium_ratio=resale_value_ratio,
        )

        # ----------------------------------------------------------
        # Phase 6: Luxury Brand Index
        # ----------------------------------------------------------
        luxury_index = None
        if is_luxury:
            luxury_index = self._calculate_luxury_index(brand, all_reviews, resale_value_ratio)

        # ----------------------------------------------------------
        # Phase 7: Confidence
        # ----------------------------------------------------------
        confidence = _compute_confidence(all_reviews, source_collections)

        result = BrandSentimentScore(
            brand_name=brand.name,
            timestamp=datetime.utcnow(),
            bss=bss_value,
            discoverability=disc,
            identity=ident,
            value_perception=val,
            connection=conn,
            love=love,
            momentum=mom,
            competitive_position=cps,
            pricing_intelligence=pricing,
            hype_health=hhi,
            luxury_index=luxury_index,
            is_luxury=is_luxury,
            data_sources_used=sources_used,
            total_data_points=all_reviews.count,
            confidence=confidence,
        )

        logger.info(
            "BSS for '%s': %.1f (%s) — %s — confidence: %.0f%%",
            brand.name, result.bss, result.grade(),
            "LUXURY" if is_luxury else "standard",
            confidence * 100,
        )

        return result

    def _detect_luxury(self, brand: Brand) -> bool:
        if self.force_luxury is not None:
            return self.force_luxury
        return brand.name.lower() in LUXURY_BRANDS

    def _calculate_luxury_index(
        self,
        brand: Brand,
        collection: ReviewCollection,
        resale_ratio: float | None,
    ) -> LuxuryBrandIndex:
        exclusivity_count = 0
        aspirational_count = 0
        devaluation_count = 0

        for review in collection.reviews:
            lower = review.text.lower()
            if any(p in lower for p in LUXURY_ASPIRATIONAL_PHRASES):
                aspirational_count += 1
            if any(p in lower for p in LUXURY_DEVALUATION_PHRASES):
                devaluation_count += 1
            if any(kw in lower for kw in ["limited edition", "exclusive", "rare", "collectible", "waiting list"]):
                exclusivity_count += 1

        total = max(1, len(collection.reviews))

        exclusivity_score = min(100, (exclusivity_count / total) * 1000)
        asp_net = (aspirational_count - devaluation_count) / total
        aspirational_score = max(0, min(100, 50 + asp_net * 500))

        heritage_kws = ["heritage", "since ", "founded", "history", "tradition", "legacy", "maison"]
        heritage_count = sum(
            1 for r in collection.reviews
            if any(kw in r.text.lower() for kw in heritage_kws)
        )
        heritage_score = min(100, (heritage_count / total) * 1000)

        composite = (
            exclusivity_score * 0.25
            + aspirational_score * 0.35
            + heritage_score * 0.15
            + (min(100, (resale_ratio or 0.5) * 100) * 0.25)
        )

        return LuxuryBrandIndex(
            brand_name=brand.name,
            resale_premium_ratio=resale_ratio or 0.0,
            exclusivity_score=exclusivity_score,
            aspirational_score=aspirational_score,
            heritage_score=heritage_score,
            composite=composite,
        )


def _compute_confidence(
    all_reviews: ReviewCollection,
    source_collections: dict[str, ReviewCollection],
) -> float:
    source_score = min(1.0, len(source_collections) / 3)
    volume_score = min(1.0, all_reviews.count / 50)
    if all_reviews.count >= 2:
        dates = sorted(r.timestamp for r in all_reviews.reviews)
        span_days = (dates[-1] - dates[0]).days
        temporal_score = min(1.0, span_days / 30)
    else:
        temporal_score = 0.0
    return source_score * 0.4 + volume_score * 0.3 + temporal_score * 0.3
