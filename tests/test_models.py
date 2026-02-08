"""Tests for data models."""

from datetime import datetime, timedelta

import pytest

from src.models.brand import Brand
from src.models.review import Review, ReviewCollection
from src.models.sentiment import SentimentResult
from src.models.score import (
    BrandSentimentScore,
    DimensionScore,
    PredictiveSignal,
    ValuePerceptionScore,
)


class TestBrand:
    def test_basic_creation(self):
        brand = Brand(name="Tesla")
        assert brand.name == "Tesla"
        assert brand.search_terms == ["Tesla"]
        assert brand.ticker is None
        assert brand.category == "general"

    def test_from_dict(self):
        data = {
            "name": "Apple",
            "ticker": "AAPL",
            "search_terms": ["Apple", "Apple Inc"],
            "wikipedia_article": "Apple_Inc.",
            "competitors": ["Samsung", "Google"],
            "category": "technology",
        }
        brand = Brand.from_dict(data)
        assert brand.name == "Apple"
        assert brand.ticker == "AAPL"
        assert len(brand.search_terms) == 2
        assert brand.wikipedia_article == "Apple_Inc."

    def test_default_search_terms(self):
        brand = Brand(name="Nike")
        assert brand.search_terms == ["Nike"]


class TestReview:
    def test_word_count_auto(self):
        r = Review(text="This is a great brand with amazing products", source="test")
        assert r.word_count == 8

    def test_empty_text(self):
        r = Review(text="", source="test")
        assert r.word_count == 0

    def test_defaults(self):
        r = Review(text="test", source="reddit")
        assert r.rating is None
        assert r.sentiment_compound is None
        assert r.engagement == 0
        assert r.is_verified is False


class TestReviewCollection:
    def _make_collection(self, n: int = 5) -> ReviewCollection:
        reviews = []
        for i in range(n):
            reviews.append(
                Review(
                    text=f"Review number {i} with some text content",
                    source="test",
                    rating=3.0 + (i % 3),
                    timestamp=datetime.utcnow() - timedelta(days=i),
                    sentiment_compound=0.1 * i,
                )
            )
        return ReviewCollection(brand_name="TestBrand", reviews=reviews)

    def test_count(self):
        c = self._make_collection(5)
        assert c.count == 5

    def test_average_rating(self):
        c = self._make_collection(3)
        assert c.average_rating is not None
        assert 3.0 <= c.average_rating <= 5.0

    def test_average_sentiment(self):
        c = self._make_collection(3)
        assert c.average_sentiment is not None

    def test_filter_by_source(self):
        c = self._make_collection(3)
        filtered = c.filter_by_source("test")
        assert filtered.count == 3
        filtered_empty = c.filter_by_source("nonexistent")
        assert filtered_empty.count == 0

    def test_empty_collection(self):
        c = ReviewCollection(brand_name="Empty")
        assert c.count == 0
        assert c.average_rating is None
        assert c.average_sentiment is None


class TestSentimentResult:
    def test_positive_label(self):
        r = SentimentResult(compound=0.5)
        assert r.label == "positive"

    def test_negative_label(self):
        r = SentimentResult(compound=-0.5)
        assert r.label == "negative"

    def test_neutral_label(self):
        r = SentimentResult(compound=0.0)
        assert r.label == "neutral"

    def test_boundary_positive(self):
        r = SentimentResult(compound=0.05)
        assert r.label == "positive"

    def test_boundary_negative(self):
        r = SentimentResult(compound=-0.05)
        assert r.label == "negative"


class TestBrandSentimentScore:
    def test_grade_a_plus(self):
        bss = BrandSentimentScore(brand_name="Test", bss=95.0)
        assert bss.grade() == "A+"

    def test_grade_a(self):
        bss = BrandSentimentScore(brand_name="Test", bss=85.0)
        assert bss.grade() == "A"

    def test_grade_f(self):
        bss = BrandSentimentScore(brand_name="Test", bss=25.0)
        assert bss.grade() == "F"

    def test_to_dict(self):
        bss = BrandSentimentScore(
            brand_name="Test",
            bss=72.5,
            value_perception=ValuePerceptionScore(value=80.0),
            data_sources_used=["google_news", "reddit"],
            total_data_points=150,
            confidence=0.85,
        )
        d = bss.to_dict()
        assert d["brand"] == "Test"
        assert d["bss"] == 72.5
        assert d["grade"] == "B+"
        assert "value_perception" in d["dimensions"]
        assert d["confidence"] == 0.85


class TestPredictiveSignal:
    def test_to_dict_basic(self):
        signal = PredictiveSignal(
            brand_name="Test",
            bss_current=70.0,
            bss_previous=65.0,
            bss_delta=5.0,
            signal="moderate_bullish",
        )
        d = signal.to_dict()
        assert d["signal"] == "moderate_bullish"
        assert d["bss_delta"] == 5.0

    def test_to_dict_with_divergence(self):
        signal = PredictiveSignal(
            brand_name="Test",
            bss_current=70.0,
            bss_previous=65.0,
            bss_delta=5.0,
            signal="moderate_bullish",
            price_change_pct=-2.5,
            sentiment_price_divergence=0.75,
            divergence_signal="undervalued",
        )
        d = signal.to_dict()
        assert d["divergence_signal"] == "undervalued"
        assert d["price_change_pct"] == -2.5


class TestDimensionScore:
    def test_clamp_to_100(self):
        d = DimensionScore(name="test", value=150.0)
        assert d.value == 100.0

    def test_clamp_to_0(self):
        d = DimensionScore(name="test", value=-10.0)
        assert d.value == 0.0

    def test_within_range(self):
        d = DimensionScore(name="test", value=55.5)
        assert d.value == 55.5
