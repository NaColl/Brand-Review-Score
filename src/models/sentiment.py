"""Sentiment analysis result model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class SentimentResult:
    """Output of the sentiment analysis pipeline for a single text.

    Attributes:
        compound:    Normalized compound score in [-1.0, 1.0].
                     -1.0 = maximally negative, +1.0 = maximally positive.
        positive:    Proportion of text that is positive [0, 1].
        negative:    Proportion of text that is negative [0, 1].
        neutral:     Proportion of text that is neutral  [0, 1].
        label:       Categorical label derived from compound score.
        confidence:  Engine-reported confidence in [0, 1] (1.0 if unavailable).
        engine:      Which NLP engine produced this result.
    """

    compound: float
    positive: float = 0.0
    negative: float = 0.0
    neutral: float = 0.0
    label: Literal["positive", "negative", "neutral"] = "neutral"
    confidence: float = 1.0
    engine: str = "vader"

    def __post_init__(self) -> None:
        # Derive label from compound if not set explicitly
        if self.compound >= 0.05:
            self.label = "positive"
        elif self.compound <= -0.05:
            self.label = "negative"
        else:
            self.label = "neutral"
