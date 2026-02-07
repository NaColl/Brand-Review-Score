"""Predictive signal generation from BSS trends.

Generates actionable signals:
1. BSS Momentum Signal — based on BSS delta over time
2. Sentiment-Price Divergence — for public companies
3. Trend Confirmation — combining multiple trend indicators

Academic basis:
- Fornell et al.: ACSI changes lead stock price changes by 1-3 months
- Bollen et al. (2011): Sentiment momentum predicts DJIA with 87.6% accuracy
- Tirunillai & Tellis (2012): Volume changes predict abnormal returns
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal

from config.settings import SIGNAL_THRESHOLDS, DIVERGENCE_THRESHOLD
from src.models.score import BrandSentimentScore, PredictiveSignal

logger = logging.getLogger(__name__)


class SignalGenerator:
    """Generates predictive signals from BSS scores and optional price data."""

    def generate(
        self,
        current_bss: BrandSentimentScore,
        previous_bss: BrandSentimentScore | None = None,
        price_change_pct: float | None = None,
    ) -> PredictiveSignal:
        """Generate a predictive signal.

        Args:
            current_bss: The current BSS calculation.
            previous_bss: BSS from ~30 days ago (for delta computation).
            price_change_pct: Stock price change over same period (public cos).
        """
        # BSS Delta
        bss_current = current_bss.bss
        bss_previous = previous_bss.bss if previous_bss else bss_current
        bss_delta = bss_current - bss_previous

        # Determine signal from delta
        signal = self._classify_signal(bss_delta)

        # Confidence based on data quality
        confidence = current_bss.confidence
        if previous_bss:
            confidence = (confidence + previous_bss.confidence) / 2

        # Sentiment-Price Divergence (public companies only)
        divergence = None
        divergence_signal = None
        if price_change_pct is not None:
            divergence, divergence_signal = self._compute_divergence(
                bss_delta, price_change_pct
            )

        explanation = self._build_explanation(
            bss_delta, signal, divergence_signal, current_bss
        )

        return PredictiveSignal(
            brand_name=current_bss.brand_name,
            timestamp=datetime.utcnow(),
            bss_current=bss_current,
            bss_previous=bss_previous,
            bss_delta=bss_delta,
            signal=signal,
            price_change_pct=price_change_pct,
            sentiment_price_divergence=divergence,
            divergence_signal=divergence_signal,
            confidence=confidence,
            explanation=explanation,
        )

    @staticmethod
    def _classify_signal(
        bss_delta: float,
    ) -> Literal[
        "strong_bullish", "moderate_bullish", "neutral",
        "moderate_bearish", "strong_bearish"
    ]:
        if bss_delta >= SIGNAL_THRESHOLDS["strong_bullish"]:
            return "strong_bullish"
        elif bss_delta >= SIGNAL_THRESHOLDS["moderate_bullish"]:
            return "moderate_bullish"
        elif bss_delta <= SIGNAL_THRESHOLDS["strong_bearish"]:
            return "strong_bearish"
        elif bss_delta <= SIGNAL_THRESHOLDS["moderate_bearish"]:
            return "moderate_bearish"
        else:
            return "neutral"

    @staticmethod
    def _compute_divergence(
        bss_delta: float,
        price_change_pct: float,
    ) -> tuple[float, Literal["undervalued", "overvalued", "aligned"]]:
        """Detect divergence between sentiment and price movement.

        If sentiment is improving but price is flat/falling → undervalued
        If sentiment is declining but price is rising → overvalued
        If both moving in same direction → aligned
        """
        # Normalize BSS delta to percentage-like scale
        # BSS delta of 10 points ≈ significant shift
        sentiment_signal = bss_delta / 10.0  # Rough normalization

        # Price change is already in percentage
        price_signal = price_change_pct / 10.0  # 10% change = significant

        divergence = sentiment_signal - price_signal

        if divergence > DIVERGENCE_THRESHOLD:
            return divergence, "undervalued"
        elif divergence < -DIVERGENCE_THRESHOLD:
            return divergence, "overvalued"
        else:
            return divergence, "aligned"

    @staticmethod
    def _build_explanation(
        bss_delta: float,
        signal: str,
        divergence_signal: str | None,
        bss: BrandSentimentScore,
    ) -> str:
        parts: list[str] = []

        # BSS summary
        parts.append(
            f"BSS: {bss.bss:.1f}/100 ({bss.grade()}) — "
            f"delta: {bss_delta:+.1f} pts"
        )

        # Signal interpretation
        signal_text = {
            "strong_bullish": "STRONG BULLISH — rapid sentiment improvement",
            "moderate_bullish": "MODERATE BULLISH — sentiment improving",
            "neutral": "NEUTRAL — sentiment stable",
            "moderate_bearish": "MODERATE BEARISH — sentiment declining",
            "strong_bearish": "STRONG BEARISH — rapid sentiment deterioration",
        }
        parts.append(signal_text.get(signal, signal))

        # Divergence
        if divergence_signal == "undervalued":
            parts.append(
                "DIVERGENCE: Sentiment rising faster than price — "
                "potential undervaluation"
            )
        elif divergence_signal == "overvalued":
            parts.append(
                "DIVERGENCE: Price rising faster than sentiment — "
                "potential overvaluation"
            )

        # Dimension highlights
        if bss.momentum and bss.momentum.value > 70:
            parts.append("Strong momentum detected")
        if bss.momentum and bss.momentum.value < 30:
            parts.append("Momentum weakness detected")

        return " | ".join(parts)
