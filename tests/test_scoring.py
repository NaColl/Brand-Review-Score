"""Tests for scoring dimensions and composite BSS."""

from datetime import datetime, timedelta

import pytest

from src.models.review import Review, ReviewCollection
from src.scoring.review_quality import calculate_review_quality
from src.scoring.social_sentiment import calculate_social_sentiment
from src.scoring.momentum import calculate_momentum
from src.scoring.brand_health import calculate_brand_health
from src.scoring.competitive import calculate_competitive_position


def _make_reviews(
    n: int,
    source: str = "test",
    rating: float = 4.0,
    sentiment: float = 0.3,
    days_spread: int = 30,
    text: str = "This is a sample review with enough words to be meaningful for testing",
    engagement: int = 10,
) -> ReviewCollection:
    """Helper to create test review collections."""
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


class TestReviewQuality:
    def test_good_reviews(self):
        collection = _make_reviews(50, rating=4.5, sentiment=0.6)
        rqs = calculate_review_quality(collection)
        assert rqs.value > 50

    def test_bad_reviews(self):
        collection = _make_reviews(50, rating=1.5, sentiment=-0.5)
        rqs = calculate_review_quality(collection)
        assert rqs.value < 50

    def test_empty_collection(self):
        collection = ReviewCollection(brand_name="Empty")
        rqs = calculate_review_quality(collection)
        assert 0 <= rqs.value <= 100

    def test_score_range(self):
        collection = _make_reviews(20)
        rqs = calculate_review_quality(collection)
        assert 0 <= rqs.value <= 100

    def test_has_components(self):
        collection = _make_reviews(20)
        rqs = calculate_review_quality(collection)
        assert "normalized_rating" in rqs.components
        assert "review_volume_health" in rqs.components
        assert "review_depth" in rqs.components
        assert "sentiment_distribution" in rqs.components


class TestSocialSentiment:
    def test_positive_social(self):
        reddit = _make_reviews(30, source="reddit", sentiment=0.5, engagement=100)
        news = _make_reviews(20, source="google_news", sentiment=0.4)
        trends = _make_reviews(10, source="google_trends", engagement=70)
        sss = calculate_social_sentiment(reddit, news, trends)
        assert sss.value > 50

    def test_negative_social(self):
        reddit = _make_reviews(30, source="reddit", sentiment=-0.5, engagement=100)
        news = _make_reviews(20, source="google_news", sentiment=-0.4)
        trends = _make_reviews(10, source="google_trends", engagement=30)
        sss = calculate_social_sentiment(reddit, news, trends)
        assert sss.value < 50

    def test_empty_sources(self):
        empty = ReviewCollection(brand_name="Empty")
        sss = calculate_social_sentiment(empty, empty, empty)
        assert 0 <= sss.value <= 100


class TestMomentum:
    def test_improving_sentiment(self):
        """Sentiment improving over time should yield high momentum."""
        now = datetime.utcnow()
        reviews = []
        for i in range(60):
            # Sentiment goes from -0.3 to +0.5 over 60 days
            sentiment = -0.3 + (i / 60) * 0.8
            reviews.append(
                Review(
                    text="review",
                    source="test",
                    sentiment_compound=sentiment,
                    timestamp=now - timedelta(days=60 - i),
                )
            )
        collection = ReviewCollection(brand_name="Test", reviews=reviews)
        ms = calculate_momentum(collection, reference_date=now)
        assert ms.value > 50

    def test_declining_sentiment(self):
        """Sentiment declining over time should yield low momentum."""
        now = datetime.utcnow()
        reviews = []
        for i in range(60):
            sentiment = 0.5 - (i / 60) * 0.8
            reviews.append(
                Review(
                    text="review",
                    source="test",
                    sentiment_compound=sentiment,
                    timestamp=now - timedelta(days=60 - i),
                )
            )
        collection = ReviewCollection(brand_name="Test", reviews=reviews)
        ms = calculate_momentum(collection, reference_date=now)
        assert ms.value < 50

    def test_empty_collection(self):
        collection = ReviewCollection(brand_name="Empty")
        ms = calculate_momentum(collection)
        assert 0 <= ms.value <= 100

    def test_has_components(self):
        collection = _make_reviews(30)
        ms = calculate_momentum(collection)
        assert "sentiment_velocity" in ms.components
        assert "volume_velocity" in ms.components
        assert "breakout_detection" in ms.components


class TestBrandHealth:
    def test_healthy_brand(self):
        reviews = _make_reviews(
            30,
            text="I highly recommend this brand. Loyal customer for years. Amazing service!",
        )
        bhi = calculate_brand_health(reviews)
        assert bhi.value > 40

    def test_unhealthy_brand(self):
        reviews = _make_reviews(
            30,
            text="Terrible product. Would not recommend. Stay away from this brand.",
        )
        bhi = calculate_brand_health(reviews)
        assert bhi.value < 60

    def test_has_components(self):
        reviews = _make_reviews(20)
        bhi = calculate_brand_health(reviews)
        assert "nps_proxy" in bhi.components
        assert "response_quality" in bhi.components
        assert "loyalty_signals" in bhi.components


class TestCompetitivePosition:
    def test_brand_leads(self):
        brand = _make_reviews(50, sentiment=0.6)
        competitors = {
            "CompA": _make_reviews(30, sentiment=0.2),
            "CompB": _make_reviews(30, sentiment=0.1),
        }
        cps = calculate_competitive_position(brand, competitors)
        assert cps.value > 50

    def test_brand_trails(self):
        brand = _make_reviews(20, sentiment=0.1)
        competitors = {
            "CompA": _make_reviews(50, sentiment=0.6),
            "CompB": _make_reviews(50, sentiment=0.5),
        }
        cps = calculate_competitive_position(brand, competitors)
        assert cps.value < 50

    def test_no_competitors(self):
        brand = _make_reviews(30, sentiment=0.4)
        cps = calculate_competitive_position(brand, {})
        assert 0 <= cps.value <= 100
