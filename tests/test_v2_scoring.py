"""Tests for v2 scoring dimensions: Discoverability, Identity, Value, Connection, Love, Pricing, HHI."""

from datetime import datetime, timedelta

import pytest

from src.models.review import Review, ReviewCollection
from src.models.score import (
    HypeHealthIndex,
    LuxuryBrandIndex,
    BrandSentimentScore,
)
from src.scoring.discoverability import calculate_discoverability
from src.scoring.identity import calculate_identity
from src.scoring.value_perception import calculate_value_perception
from src.scoring.connection import calculate_connection
from src.scoring.love import calculate_love
from src.scoring.pricing_intelligence import calculate_pricing_intelligence
from src.scoring.hype_health import calculate_hype_health


def _make_reviews(
    n: int,
    source: str = "test",
    rating: float | None = 4.0,
    sentiment: float = 0.3,
    days_spread: int = 30,
    text: str = "This is a sample review with enough words to be meaningful",
    engagement: int = 10,
) -> ReviewCollection:
    now = datetime.utcnow()
    reviews = []
    for i in range(n):
        reviews.append(
            Review(
                text=text,
                source=source,
                rating=rating,
                sentiment_compound=sentiment,
                timestamp=now - timedelta(days=i * days_spread / max(n, 1)),
                engagement=engagement,
            )
        )
    return ReviewCollection(brand_name="TestBrand", reviews=reviews)


# ──────────────────────────────────────────────────────────────
# Discoverability
# ──────────────────────────────────────────────────────────────

class TestDiscoverability:
    def test_high_discoverability(self):
        news = _make_reviews(30, source="google_news")
        reddit = _make_reviews(50, source="reddit", engagement=50)
        trends = _make_reviews(20, source="google_trends", engagement=80)
        wiki = _make_reviews(30, source="wikipedia", engagement=5000)
        score = calculate_discoverability(news, reddit, trends, wiki)
        assert score.value > 40

    def test_zero_data(self):
        empty = ReviewCollection(brand_name="Empty")
        score = calculate_discoverability(empty, empty, empty, empty)
        assert 0 <= score.value <= 100

    def test_components_present(self):
        news = _make_reviews(5, source="google_news")
        empty = ReviewCollection(brand_name="Empty")
        score = calculate_discoverability(news, empty, empty, empty)
        assert "search_volume" in score.components
        assert "news_volume" in score.components


# ──────────────────────────────────────────────────────────────
# Identity
# ──────────────────────────────────────────────────────────────

class TestIdentity:
    def test_positive_narrative(self):
        news = _make_reviews(20, source="google_news", sentiment=0.6)
        all_data = _make_reviews(50, sentiment=0.5, text="sustainable eco-friendly innovation")
        score = calculate_identity(all_data, news, brand_values=["sustainability", "innovation"])
        assert score.value > 40

    def test_negative_narrative(self):
        news = _make_reviews(20, source="google_news", sentiment=-0.5)
        all_data = _make_reviews(50, sentiment=-0.3)
        score = calculate_identity(all_data, news)
        assert score.value < 60

    def test_empty(self):
        empty = ReviewCollection(brand_name="Empty")
        score = calculate_identity(empty, empty)
        assert 0 <= score.value <= 100


# ──────────────────────────────────────────────────────────────
# Value Perception
# ──────────────────────────────────────────────────────────────

class TestValuePerception:
    def test_high_value(self):
        reviews = _make_reviews(
            30, rating=4.5, text="worth every penny, great quality, investment piece"
        )
        score = calculate_value_perception(reviews, resale_premium_ratio=1.1)
        assert score.value > 50

    def test_low_value(self):
        reviews = _make_reviews(
            30, rating=1.5, text="overpriced waste of money, too expensive, not worth"
        )
        score = calculate_value_perception(reviews, resale_premium_ratio=0.3)
        assert score.value < 50

    def test_no_resale_data(self):
        reviews = _make_reviews(20, rating=3.5)
        score = calculate_value_perception(reviews)
        assert 0 <= score.value <= 100


# ──────────────────────────────────────────────────────────────
# Connection
# ──────────────────────────────────────────────────────────────

class TestConnection:
    def test_high_engagement(self):
        reviews = _make_reviews(
            30, engagement=200, sentiment=0.8,
            text="game changer! blew my mind, everyone needs to know about this"
        )
        score = calculate_connection(reviews)
        assert score.value > 50

    def test_low_engagement(self):
        reviews = _make_reviews(10, engagement=1, sentiment=0.0)
        score = calculate_connection(reviews)
        assert score.value < 60

    def test_empty(self):
        empty = ReviewCollection(brand_name="Empty")
        score = calculate_connection(empty)
        assert 0 <= score.value <= 100


# ──────────────────────────────────────────────────────────────
# Love
# ──────────────────────────────────────────────────────────────

class TestLove:
    def test_strong_love(self):
        reviews = _make_reviews(
            30, sentiment=0.8,
            text="I highly recommend this, obsessed with it, loyal for years, can't live without it"
        )
        score = calculate_love(reviews)
        assert score.value > 50

    def test_weak_love(self):
        reviews = _make_reviews(
            30, sentiment=-0.3,
            text="terrible, would not recommend, stay away, worst product ever"
        )
        score = calculate_love(reviews)
        assert score.value < 50

    def test_components(self):
        reviews = _make_reviews(20)
        score = calculate_love(reviews)
        assert "nps_proxy" in score.components
        assert "loyalty_signals" in score.components
        assert "emotional_attachment" in score.components


# ──────────────────────────────────────────────────────────────
# Pricing Intelligence
# ──────────────────────────────────────────────────────────────

class TestPricingIntelligence:
    def test_healthy_pricing(self):
        reviews = _make_reviews(20, text="worth every penny, fair price, investment piece")
        score = calculate_pricing_intelligence(
            reviews, sale_percentage=0.05, avg_discount_pct=0.10, resale_value_ratio=1.1
        )
        assert score.value > 60

    def test_struggling_pricing(self):
        reviews = _make_reviews(20, text="overpriced, waste of money, too expensive")
        score = calculate_pricing_intelligence(
            reviews, sale_percentage=0.50, avg_discount_pct=0.60, resale_value_ratio=0.3
        )
        assert score.value < 40

    def test_no_pricing_data(self):
        reviews = _make_reviews(20)
        score = calculate_pricing_intelligence(reviews)
        assert 0 <= score.value <= 100

    def test_sale_alert(self):
        """40%+ on sale should trigger low score for sale_percentage component."""
        reviews = _make_reviews(10)
        score = calculate_pricing_intelligence(reviews, sale_percentage=0.45)
        assert score.components["sale_percentage"] < 0.3


# ──────────────────────────────────────────────────────────────
# Hype vs Health Index
# ──────────────────────────────────────────────────────────────

class TestHypeHealth:
    def test_strong_brand(self):
        trends = _make_reviews(20, source="google_trends", engagement=80)
        reddit = _make_reviews(50, source="reddit")
        news = _make_reviews(30, source="google_news")
        wiki = _make_reviews(30, source="wikipedia", engagement=10000)
        hhi = calculate_hype_health(
            trends, reddit, news, wiki,
            stock_momentum=10.0, resale_premium_ratio=1.0, sale_percentage=0.05,
        )
        assert hhi.hype_score > 40
        assert hhi.health_score > 40

    def test_overhyped(self):
        trends = _make_reviews(20, source="google_trends", engagement=90)
        reddit = _make_reviews(100, source="reddit")
        news = _make_reviews(40, source="google_news")
        wiki = _make_reviews(30, source="wikipedia", engagement=50000)
        hhi = calculate_hype_health(
            trends, reddit, news, wiki,
            stock_momentum=-15.0, sale_percentage=0.50, resale_premium_ratio=0.3,
        )
        assert hhi.hype_score > hhi.health_score

    def test_quadrants(self):
        hhi = HypeHealthIndex(hype_score=80, health_score=80)
        assert hhi.quadrant == "strong_brand"

        hhi = HypeHealthIndex(hype_score=80, health_score=20)
        assert hhi.quadrant == "overhyped"

        hhi = HypeHealthIndex(hype_score=20, health_score=80)
        assert hhi.quadrant == "hidden_gem"

        hhi = HypeHealthIndex(hype_score=20, health_score=20)
        assert hhi.quadrant == "declining"

    def test_divergence(self):
        hhi = HypeHealthIndex(hype_score=80, health_score=40)
        assert hhi.divergence == 40.0


# ──────────────────────────────────────────────────────────────
# Luxury Brand Index
# ──────────────────────────────────────────────────────────────

class TestLuxuryBrandIndex:
    def test_to_dict(self):
        lux = LuxuryBrandIndex(
            brand_name="Hermes",
            resale_premium_ratio=1.3,
            exclusivity_score=90,
            aspirational_score=85,
            heritage_score=95,
            composite=88,
        )
        d = lux.to_dict()
        assert d["brand"] == "Hermes"
        assert d["resale_premium_ratio"] == 1.3
        assert d["luxury_index"] == 88


# ──────────────────────────────────────────────────────────────
# BSS v2 model
# ──────────────────────────────────────────────────────────────

class TestBSSv2Model:
    def test_to_dict_includes_all_dimensions(self):
        from src.models.score import (
            DiscoverabilityScore,
            IdentityScore,
            ValuePerceptionScore,
            ConnectionScore,
            LoveScore,
            MomentumScore,
            CompetitivePositionScore,
            PricingIntelligenceScore,
        )
        bss = BrandSentimentScore(
            brand_name="Test",
            bss=72.5,
            discoverability=DiscoverabilityScore(value=65),
            identity=IdentityScore(value=70),
            value_perception=ValuePerceptionScore(value=75),
            connection=ConnectionScore(value=68),
            love=LoveScore(value=72),
            momentum=MomentumScore(value=80),
            competitive_position=CompetitivePositionScore(value=60),
            pricing_intelligence=PricingIntelligenceScore(value=55),
            is_luxury=True,
        )
        d = bss.to_dict()
        assert d["is_luxury"] is True
        assert len(d["dimensions"]) == 8
        assert "discoverability" in d["dimensions"]
        assert "pricing_intelligence" in d["dimensions"]

    def test_legacy_aliases(self):
        from src.models.score import ValuePerceptionScore, DiscoverabilityScore, LoveScore
        bss = BrandSentimentScore(
            brand_name="Test",
            value_perception=ValuePerceptionScore(value=75),
            discoverability=DiscoverabilityScore(value=65),
            love=LoveScore(value=70),
        )
        assert bss.review_quality is bss.value_perception
        assert bss.social_sentiment is bss.discoverability
        assert bss.brand_health is bss.love

    def test_hhi_in_output(self):
        hhi = HypeHealthIndex(brand_name="Test", hype_score=70, health_score=80)
        bss = BrandSentimentScore(brand_name="Test", bss=65, hype_health=hhi)
        d = bss.to_dict()
        assert "hype_health_index" in d
        assert d["hype_health_index"]["quadrant"] == "strong_brand"
