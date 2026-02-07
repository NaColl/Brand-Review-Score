"""Multi-engine sentiment analysis pipeline.

Engine priority (fast → accurate):
1. VADER  — rule-based, instant, always available
2. TextBlob — pattern-based, fast, always available
3. FinBERT — transformer, high accuracy for financial text (optional)

The pipeline runs the best available engine and returns a SentimentResult.
For ensemble mode, it averages across all available engines.
"""

from __future__ import annotations

import logging
from typing import Literal

from src.analysis.nlp_utils import preprocess_text
from src.models.review import Review, ReviewCollection
from src.models.sentiment import SentimentResult

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """Runs sentiment analysis on reviews using the best available NLP engine."""

    def __init__(
        self,
        engine: Literal["vader", "textblob", "finbert", "ensemble"] = "vader",
    ) -> None:
        self.engine = engine
        self._vader = None
        self._finbert = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, text: str) -> SentimentResult:
        """Analyze a single text string."""
        cleaned = preprocess_text(text)
        if not cleaned:
            return SentimentResult(compound=0.0, engine=self.engine)

        if self.engine == "ensemble":
            return self._ensemble(cleaned)
        elif self.engine == "textblob":
            return self._analyze_textblob(cleaned)
        elif self.engine == "finbert":
            return self._analyze_finbert(cleaned)
        else:
            return self._analyze_vader(cleaned)

    def analyze_review(self, review: Review) -> Review:
        """Analyze a Review and fill its sentiment fields in-place."""
        result = self.analyze(review.text)
        review.sentiment_compound = result.compound
        review.sentiment_label = result.label
        return review

    def analyze_collection(self, collection: ReviewCollection) -> ReviewCollection:
        """Analyze all reviews in a collection."""
        for review in collection.reviews:
            self.analyze_review(review)
        return collection

    # ------------------------------------------------------------------
    # VADER
    # ------------------------------------------------------------------

    def _get_vader(self):
        if self._vader is None:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            self._vader = SentimentIntensityAnalyzer()
        return self._vader

    def _analyze_vader(self, text: str) -> SentimentResult:
        try:
            analyzer = self._get_vader()
            scores = analyzer.polarity_scores(text)
            return SentimentResult(
                compound=scores["compound"],
                positive=scores["pos"],
                negative=scores["neg"],
                neutral=scores["neu"],
                engine="vader",
            )
        except Exception as exc:
            logger.warning("VADER failed: %s", exc)
            return SentimentResult(compound=0.0, engine="vader")

    # ------------------------------------------------------------------
    # TextBlob
    # ------------------------------------------------------------------

    def _analyze_textblob(self, text: str) -> SentimentResult:
        try:
            from textblob import TextBlob
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity       # -1 to 1
            subjectivity = blob.sentiment.subjectivity  # 0 to 1

            # Map polarity to VADER-like component scores
            pos = max(0, polarity)
            neg = abs(min(0, polarity))
            neu = 1.0 - pos - neg

            return SentimentResult(
                compound=polarity,
                positive=pos,
                negative=neg,
                neutral=max(0, neu),
                confidence=subjectivity,  # Higher subjectivity = more opinionated
                engine="textblob",
            )
        except Exception as exc:
            logger.warning("TextBlob failed: %s — falling back to VADER", exc)
            return self._analyze_vader(text)

    # ------------------------------------------------------------------
    # FinBERT (optional — requires transformers + torch)
    # ------------------------------------------------------------------

    def _get_finbert(self):
        if self._finbert is None:
            try:
                from transformers import pipeline
                self._finbert = pipeline(
                    "sentiment-analysis",
                    model="ProsusAI/finbert",
                    top_k=None,
                )
            except ImportError:
                logger.warning(
                    "transformers/torch not installed — FinBERT unavailable. "
                    "Install with: pip install transformers torch"
                )
                raise
        return self._finbert

    def _analyze_finbert(self, text: str) -> SentimentResult:
        try:
            classifier = self._get_finbert()
            # FinBERT returns: [{'label': 'positive', 'score': 0.97}, ...]
            results = classifier(text[:512])  # FinBERT max 512 tokens

            # results is a list of lists when top_k=None
            scores_list = results[0] if results and isinstance(results[0], list) else results
            score_map: dict[str, float] = {}
            for item in scores_list:
                score_map[item["label"]] = item["score"]

            pos = score_map.get("positive", 0.0)
            neg = score_map.get("negative", 0.0)
            neu = score_map.get("neutral", 0.0)

            # Derive compound: positive pushes up, negative pushes down
            compound = pos - neg

            return SentimentResult(
                compound=compound,
                positive=pos,
                negative=neg,
                neutral=neu,
                confidence=max(pos, neg, neu),
                engine="finbert",
            )
        except Exception as exc:
            logger.warning("FinBERT failed: %s — falling back to VADER", exc)
            return self._analyze_vader(text)

    # ------------------------------------------------------------------
    # Ensemble (average all available engines)
    # ------------------------------------------------------------------

    def _ensemble(self, text: str) -> SentimentResult:
        results: list[SentimentResult] = []

        # VADER — always available
        results.append(self._analyze_vader(text))

        # TextBlob — always available
        try:
            results.append(self._analyze_textblob(text))
        except Exception:
            pass

        # FinBERT — optional
        try:
            results.append(self._analyze_finbert(text))
        except Exception:
            pass

        if not results:
            return SentimentResult(compound=0.0, engine="ensemble")

        avg_compound = sum(r.compound for r in results) / len(results)
        avg_pos = sum(r.positive for r in results) / len(results)
        avg_neg = sum(r.negative for r in results) / len(results)
        avg_neu = sum(r.neutral for r in results) / len(results)

        return SentimentResult(
            compound=avg_compound,
            positive=avg_pos,
            negative=avg_neg,
            neutral=avg_neu,
            confidence=sum(r.confidence for r in results) / len(results),
            engine=f"ensemble({','.join(r.engine for r in results)})",
        )
