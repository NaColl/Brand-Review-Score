"""Trend detection algorithms for brand sentiment time series.

Implements multiple complementary trend detection methods:
1. Linear regression slope
2. Exponential moving average crossover
3. Change-point detection (CUSUM-inspired)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

import numpy as np

from src.models.review import ReviewCollection


@dataclass
class TrendResult:
    """Result of trend analysis on a time series."""

    direction: Literal["up", "down", "flat"]
    slope: float                    # Linear regression slope
    r_squared: float               # Goodness of fit
    ema_signal: Literal["bullish", "bearish", "neutral"]
    change_points: list[datetime]  # Detected structural breaks
    explanation: str = ""


class TrendDetector:
    """Detects trends in brand sentiment/volume time series."""

    def __init__(self, min_data_points: int = 10) -> None:
        self.min_data_points = min_data_points

    def detect(
        self,
        collection: ReviewCollection,
        metric: Literal["sentiment", "volume"] = "sentiment",
        window_days: int = 30,
    ) -> TrendResult:
        """Run full trend analysis on the collection.

        Args:
            collection: Review data to analyze.
            metric: "sentiment" or "volume".
            window_days: How many days of history to analyze.
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(days=window_days)

        if metric == "sentiment":
            data = self._extract_sentiment_series(collection, cutoff)
        else:
            data = self._extract_volume_series(collection, cutoff, window_days)

        if len(data) < self.min_data_points:
            return TrendResult(
                direction="flat",
                slope=0.0,
                r_squared=0.0,
                ema_signal="neutral",
                change_points=[],
                explanation=f"Insufficient data ({len(data)} points, need {self.min_data_points})",
            )

        x = np.arange(len(data), dtype=float)
        y = np.array(data, dtype=float)

        slope, r_squared = self._linear_regression(x, y)
        ema_signal = self._ema_crossover(y)
        change_points = self._detect_change_points(y, cutoff)

        # Determine direction
        if slope > 0.001 and r_squared > 0.1:
            direction = "up"
        elif slope < -0.001 and r_squared > 0.1:
            direction = "down"
        else:
            direction = "flat"

        explanation = self._build_explanation(direction, slope, r_squared, ema_signal, change_points)

        return TrendResult(
            direction=direction,
            slope=slope,
            r_squared=r_squared,
            ema_signal=ema_signal,
            change_points=change_points,
            explanation=explanation,
        )

    def _extract_sentiment_series(
        self, collection: ReviewCollection, cutoff: datetime
    ) -> list[float]:
        """Extract daily average sentiment values."""
        daily: dict[str, list[float]] = {}
        for r in collection.reviews:
            if r.timestamp >= cutoff and r.sentiment_compound is not None:
                day_key = r.timestamp.strftime("%Y-%m-%d")
                daily.setdefault(day_key, []).append(r.sentiment_compound)

        # Sort by date and return daily averages
        sorted_days = sorted(daily.keys())
        return [sum(daily[d]) / len(daily[d]) for d in sorted_days]

    def _extract_volume_series(
        self, collection: ReviewCollection, cutoff: datetime, window_days: int
    ) -> list[float]:
        """Extract daily mention counts."""
        daily: dict[str, int] = {}
        for r in collection.reviews:
            if r.timestamp >= cutoff:
                day_key = r.timestamp.strftime("%Y-%m-%d")
                daily[day_key] = daily.get(day_key, 0) + 1

        # Fill missing days with 0
        sorted_days = sorted(daily.keys())
        if not sorted_days:
            return []

        return [float(daily.get(d, 0)) for d in sorted_days]

    @staticmethod
    def _linear_regression(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
        """Simple linear regression returning slope and R²."""
        n = len(x)
        if n < 2:
            return 0.0, 0.0

        x_mean = np.mean(x)
        y_mean = np.mean(y)

        ss_xy = np.sum((x - x_mean) * (y - y_mean))
        ss_xx = np.sum((x - x_mean) ** 2)
        ss_yy = np.sum((y - y_mean) ** 2)

        if ss_xx == 0:
            return 0.0, 0.0

        slope = float(ss_xy / ss_xx)

        if ss_yy == 0:
            r_squared = 0.0
        else:
            r_squared = float((ss_xy ** 2) / (ss_xx * ss_yy))

        return slope, r_squared

    @staticmethod
    def _ema_crossover(y: np.ndarray) -> Literal["bullish", "bearish", "neutral"]:
        """Detect EMA crossover signal (short EMA vs long EMA).

        - Short EMA > Long EMA → bullish (uptrend)
        - Short EMA < Long EMA → bearish (downtrend)
        """
        if len(y) < 10:
            return "neutral"

        short_span = min(7, len(y) // 2)
        long_span = min(21, len(y))

        short_ema = _ema(y, short_span)
        long_ema = _ema(y, long_span)

        if short_ema > long_ema * 1.02:
            return "bullish"
        elif short_ema < long_ema * 0.98:
            return "bearish"
        else:
            return "neutral"

    def _detect_change_points(
        self, y: np.ndarray, cutoff: datetime
    ) -> list[datetime]:
        """CUSUM-inspired change point detection.

        Detects points where the cumulative sum of deviations from the
        mean exceeds a threshold, indicating a structural break.
        """
        if len(y) < 10:
            return []

        mean = np.mean(y)
        std = np.std(y)
        if std < 0.01:
            return []

        threshold = 2.0 * std
        cusum_pos = 0.0
        cusum_neg = 0.0
        change_points: list[datetime] = []

        for i, val in enumerate(y):
            cusum_pos = max(0, cusum_pos + (val - mean) - 0.5 * std)
            cusum_neg = max(0, cusum_neg - (val - mean) - 0.5 * std)

            if cusum_pos > threshold or cusum_neg > threshold:
                # Change point detected
                cp_date = cutoff + timedelta(days=i)
                change_points.append(cp_date)
                # Reset
                cusum_pos = 0.0
                cusum_neg = 0.0

        return change_points

    @staticmethod
    def _build_explanation(
        direction: str,
        slope: float,
        r_squared: float,
        ema_signal: str,
        change_points: list[datetime],
    ) -> str:
        parts = [f"Trend: {direction} (slope={slope:.4f}, R²={r_squared:.2f})"]
        parts.append(f"EMA signal: {ema_signal}")
        if change_points:
            parts.append(f"Change points detected: {len(change_points)}")
        return "; ".join(parts)


def _ema(data: np.ndarray, span: int) -> float:
    """Calculate the current EMA value for a given span."""
    if len(data) == 0:
        return 0.0

    alpha = 2.0 / (span + 1)
    ema_val = float(data[0])
    for val in data[1:]:
        ema_val = alpha * float(val) + (1 - alpha) * ema_val
    return ema_val
