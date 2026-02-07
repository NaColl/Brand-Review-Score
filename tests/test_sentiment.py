"""Tests for sentiment analysis pipeline."""

import pytest

from src.analysis.sentiment import SentimentAnalyzer
from src.analysis.nlp_utils import (
    preprocess_text,
    extract_aspects,
    count_promoter_signals,
    count_detractor_signals,
)
from src.models.review import Review, ReviewCollection


class TestPreprocessText:
    def test_lowercases(self):
        assert preprocess_text("HELLO WORLD") == "hello world"

    def test_removes_urls(self):
        result = preprocess_text("Check https://example.com for details")
        assert "https" not in result
        assert "example.com" not in result

    def test_preserves_sentiment_punctuation(self):
        result = preprocess_text("Amazing! Really? Yes!")
        assert "!" in result
        assert "?" in result

    def test_empty_string(self):
        assert preprocess_text("") == ""

    def test_collapses_whitespace(self):
        result = preprocess_text("too   many    spaces")
        assert result == "too many spaces"


class TestExtractAspects:
    def test_quality_detected(self):
        aspects = extract_aspects("The build quality is excellent")
        assert aspects["quality"] is True

    def test_service_detected(self):
        aspects = extract_aspects("Customer service was terrible")
        assert aspects["service"] is True

    def test_value_detected(self):
        aspects = extract_aspects("This product is overpriced")
        assert aspects["value"] is True

    def test_no_aspects(self):
        aspects = extract_aspects("The sky is blue today")
        assert not any(aspects.values())


class TestPromotorDetractorSignals:
    def test_promoter_phrases(self):
        text = "I would highly recommend this to everyone. Five stars!"
        count = count_promoter_signals(text, [
            "highly recommend", "five stars", "love this",
        ])
        assert count == 2

    def test_detractor_phrases(self):
        text = "Terrible experience. I would not recommend this. Avoid!"
        count = count_detractor_signals(text, [
            "terrible", "would not recommend", "avoid",
        ])
        assert count == 3

    def test_no_signals(self):
        text = "The product arrived on time."
        assert count_promoter_signals(text, ["highly recommend"]) == 0
        assert count_detractor_signals(text, ["terrible"]) == 0


class TestSentimentAnalyzer:
    def test_vader_positive(self):
        analyzer = SentimentAnalyzer(engine="vader")
        result = analyzer.analyze("This is absolutely fantastic and amazing!")
        assert result.compound > 0
        assert result.label == "positive"
        assert result.engine == "vader"

    def test_vader_negative(self):
        analyzer = SentimentAnalyzer(engine="vader")
        result = analyzer.analyze("This is terrible and awful, worst ever.")
        assert result.compound < 0
        assert result.label == "negative"

    def test_vader_neutral(self):
        analyzer = SentimentAnalyzer(engine="vader")
        result = analyzer.analyze("The meeting is scheduled for Tuesday.")
        assert abs(result.compound) < 0.3

    def test_empty_text(self):
        analyzer = SentimentAnalyzer(engine="vader")
        result = analyzer.analyze("")
        assert result.compound == 0.0

    def test_analyze_review(self):
        analyzer = SentimentAnalyzer(engine="vader")
        review = Review(text="Great product, love it!", source="test")
        analyzer.analyze_review(review)
        assert review.sentiment_compound is not None
        assert review.sentiment_compound > 0
        assert review.sentiment_label == "positive"

    def test_analyze_collection(self):
        analyzer = SentimentAnalyzer(engine="vader")
        collection = ReviewCollection(
            brand_name="Test",
            reviews=[
                Review(text="Amazing product!", source="test"),
                Review(text="Terrible service.", source="test"),
                Review(text="It's okay.", source="test"),
            ],
        )
        analyzer.analyze_collection(collection)
        assert all(r.sentiment_compound is not None for r in collection.reviews)
        assert collection.reviews[0].sentiment_compound > collection.reviews[1].sentiment_compound
