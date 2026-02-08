"""Review data model — individual reviews and collections."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class Review:
    """A single review or social mention.

    This is the universal container for any text-based brand signal:
    product reviews, Reddit comments, news headlines, etc.
    """

    text: str
    source: str                                        # e.g. "reddit", "google_news", "app_store"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    rating: float | None = None                        # Star rating if available (1-5 scale)
    author: str | None = None
    url: str | None = None
    engagement: int = 0                                # Upvotes, likes, etc.
    is_verified: bool = False                          # Verified purchase / authenticated
    word_count: int = 0
    sentiment_compound: float | None = None            # Filled by analysis pipeline
    sentiment_label: Literal["positive", "negative", "neutral"] | None = None

    def __post_init__(self) -> None:
        if self.word_count == 0 and self.text:
            self.word_count = len(self.text.split())


@dataclass
class ReviewCollection:
    """A collection of reviews for a single brand from one or more sources."""

    brand_name: str
    reviews: list[Review] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.reviews)

    @property
    def average_rating(self) -> float | None:
        rated = [r.rating for r in self.reviews if r.rating is not None]
        return sum(rated) / len(rated) if rated else None

    @property
    def average_sentiment(self) -> float | None:
        scored = [r.sentiment_compound for r in self.reviews if r.sentiment_compound is not None]
        return sum(scored) / len(scored) if scored else None

    @property
    def average_word_count(self) -> float:
        if not self.reviews:
            return 0.0
        return sum(r.word_count for r in self.reviews) / len(self.reviews)

    def filter_by_source(self, source: str) -> ReviewCollection:
        return ReviewCollection(
            brand_name=self.brand_name,
            reviews=[r for r in self.reviews if r.source == source],
        )

    def filter_by_date_range(
        self, start: datetime, end: datetime
    ) -> ReviewCollection:
        return ReviewCollection(
            brand_name=self.brand_name,
            reviews=[r for r in self.reviews if start <= r.timestamp <= end],
        )

    def sorted_by_date(self, ascending: bool = True) -> ReviewCollection:
        return ReviewCollection(
            brand_name=self.brand_name,
            reviews=sorted(self.reviews, key=lambda r: r.timestamp, reverse=not ascending),
        )
