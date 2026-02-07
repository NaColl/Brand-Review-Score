"""Tests for trend detection and predictive signals."""

from datetime import datetime, timedelta

import pytest

from src.models.review import Review, ReviewCollection
from src.models.score import BrandSentimentScore
from src.prediction.trends import TrendDetector
from src.prediction.signals import SignalGenerator


class TestTrendDetector:
    def _make_trending_collection(
        self, direction: str = "up", n_days: int = 60
    ) -> ReviewCollection:
        now = datetime.utcnow()
        reviews = []
        for i in range(n_days):
            if direction == "up":
                sentiment = -0.2 + (i / n_days) * 0.7
            elif direction == "down":
                sentiment = 0.5 - (i / n_days) * 0.7
            else:
                sentiment = 0.2

            reviews.append(
                Review(
                    text="test review",
                    source="test",
                    sentiment_compound=sentiment,
                    timestamp=now - timedelta(days=n_days - i),
                )
            )
        return ReviewCollection(brand_name="Test", reviews=reviews)

    def test_uptrend_detection(self):
        detector = TrendDetector(min_data_points=5)
        collection = self._make_trending_collection("up", 60)
        result = detector.detect(collection, metric="sentiment", window_days=60)
        assert result.direction == "up"
        assert result.slope > 0

    def test_downtrend_detection(self):
        detector = TrendDetector(min_data_points=5)
        collection = self._make_trending_collection("down", 60)
        result = detector.detect(collection, metric="sentiment", window_days=60)
        assert result.direction == "down"
        assert result.slope < 0

    def test_insufficient_data(self):
        detector = TrendDetector(min_data_points=10)
        collection = ReviewCollection(brand_name="Empty")
        result = detector.detect(collection)
        assert result.direction == "flat"
        assert "Insufficient" in result.explanation

    def test_flat_trend(self):
        detector = TrendDetector(min_data_points=5)
        collection = self._make_trending_collection("flat", 60)
        result = detector.detect(collection, metric="sentiment", window_days=60)
        assert result.direction == "flat"


class TestSignalGenerator:
    def test_strong_bullish(self):
        gen = SignalGenerator()
        current = BrandSentimentScore(brand_name="Test", bss=78.0, confidence=0.8)
        previous = BrandSentimentScore(brand_name="Test", bss=68.0, confidence=0.7)
        signal = gen.generate(current, previous)
        assert signal.signal == "strong_bullish"
        assert signal.bss_delta == 10.0

    def test_moderate_bullish(self):
        gen = SignalGenerator()
        current = BrandSentimentScore(brand_name="Test", bss=68.0, confidence=0.8)
        previous = BrandSentimentScore(brand_name="Test", bss=63.0, confidence=0.7)
        signal = gen.generate(current, previous)
        assert signal.signal == "moderate_bullish"

    def test_neutral(self):
        gen = SignalGenerator()
        current = BrandSentimentScore(brand_name="Test", bss=65.0, confidence=0.8)
        previous = BrandSentimentScore(brand_name="Test", bss=64.0, confidence=0.7)
        signal = gen.generate(current, previous)
        assert signal.signal == "neutral"

    def test_moderate_bearish(self):
        gen = SignalGenerator()
        current = BrandSentimentScore(brand_name="Test", bss=60.0, confidence=0.8)
        previous = BrandSentimentScore(brand_name="Test", bss=65.0, confidence=0.7)
        signal = gen.generate(current, previous)
        assert signal.signal == "moderate_bearish"

    def test_strong_bearish(self):
        gen = SignalGenerator()
        current = BrandSentimentScore(brand_name="Test", bss=50.0, confidence=0.8)
        previous = BrandSentimentScore(brand_name="Test", bss=60.0, confidence=0.7)
        signal = gen.generate(current, previous)
        assert signal.signal == "strong_bearish"

    def test_no_previous(self):
        gen = SignalGenerator()
        current = BrandSentimentScore(brand_name="Test", bss=70.0, confidence=0.8)
        signal = gen.generate(current)
        assert signal.signal == "neutral"
        assert signal.bss_delta == 0.0

    def test_undervalued_divergence(self):
        gen = SignalGenerator()
        current = BrandSentimentScore(brand_name="Test", bss=78.0, confidence=0.8)
        previous = BrandSentimentScore(brand_name="Test", bss=68.0, confidence=0.7)
        signal = gen.generate(current, previous, price_change_pct=-5.0)
        assert signal.divergence_signal == "undervalued"

    def test_overvalued_divergence(self):
        gen = SignalGenerator()
        current = BrandSentimentScore(brand_name="Test", bss=52.0, confidence=0.8)
        previous = BrandSentimentScore(brand_name="Test", bss=60.0, confidence=0.7)
        signal = gen.generate(current, previous, price_change_pct=15.0)
        assert signal.divergence_signal == "overvalued"

    def test_aligned(self):
        gen = SignalGenerator()
        current = BrandSentimentScore(brand_name="Test", bss=70.0, confidence=0.8)
        previous = BrandSentimentScore(brand_name="Test", bss=65.0, confidence=0.7)
        signal = gen.generate(current, previous, price_change_pct=5.0)
        assert signal.divergence_signal == "aligned"
