"""Dimension 3 — Momentum Score (MS).

The most predictive dimension per academic research (Bollen et al. 2011,
Tetlock 2007, Tirunillai & Tellis 2012).

It measures CHANGE, not level. A brand with 3.5/5 trending up is more
bullish than one at 4.5/5 trending down.

Components:
    1. Sentiment Velocity (40%) — Rate of change in average sentiment
    2. Volume Velocity (30%) — Rate of change in mention volume
    3. Breakout Detection (30%) — Z-score anomaly detection
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from config.settings import (
    MS_WEIGHTS,
    MOMENTUM_WINDOWS,
    BREAKOUT_ZSCORE_THRESHOLD,
    BREAKOUT_LOOKBACK_DAYS,
)
from src.models.review import ReviewCollection
from src.models.score import MomentumScore


def calculate_momentum(
    collection: ReviewCollection,
    reference_date: datetime | None = None,
) -> MomentumScore:
    """Calculate the Momentum Score from sentiment/volume changes."""
    now = reference_date or datetime.utcnow()
    components: dict[str, float] = {}

    # ---- 1. Sentiment Velocity ----
    components["sentiment_velocity"] = _sentiment_velocity(collection, now)

    # ---- 2. Volume Velocity ----
    components["volume_velocity"] = _volume_velocity(collection, now)

    # ---- 3. Breakout Detection ----
    components["breakout_detection"] = _breakout_detection(collection, now)

    # Weighted sum → 0–100
    value = sum(
        components[k] * MS_WEIGHTS[k] * 100
        for k in MS_WEIGHTS
    )

    explanation = _build_explanation(components)

    return MomentumScore(
        value=value,
        components=components,
        explanation=explanation,
    )


def _sentiment_velocity(collection: ReviewCollection, now: datetime) -> float:
    """Rate of change in average sentiment across multiple time windows.

    Computes velocity for 7d, 14d, and 30d windows, then averages.
    Positive velocity → improving sentiment → score > 0.5
    Negative velocity → declining sentiment → score < 0.5
    """
    velocities: list[float] = []

    for window_name, days in MOMENTUM_WINDOWS.items():
        recent_start = now - timedelta(days=days)
        older_start = now - timedelta(days=days * 2)

        recent = [
            r.sentiment_compound
            for r in collection.reviews
            if r.sentiment_compound is not None and r.timestamp >= recent_start
        ]
        older = [
            r.sentiment_compound
            for r in collection.reviews
            if r.sentiment_compound is not None and older_start <= r.timestamp < recent_start
        ]

        if recent and older:
            recent_avg = sum(recent) / len(recent)
            older_avg = sum(older) / len(older)
            # Velocity: change per period, normalized
            if abs(older_avg) > 0.01:
                velocity = (recent_avg - older_avg) / abs(older_avg)
            else:
                velocity = recent_avg - older_avg
            velocities.append(velocity)

    if not velocities:
        return 0.5  # No momentum data → neutral

    avg_velocity = sum(velocities) / len(velocities)

    # Map velocity to [0, 1]: clip at ±1 and shift
    # velocity of +0.5 → 0.75, velocity of -0.5 → 0.25
    return max(0.0, min(1.0, 0.5 + avg_velocity * 0.5))


def _volume_velocity(collection: ReviewCollection, now: datetime) -> float:
    """Rate of change in mention volume.

    Volume acceleration is a leading indicator:
    - Rapid increase → growing attention (could be positive or negative)
    - Combined with sentiment velocity, this disambiguates
    """
    velocities: list[float] = []

    for window_name, days in MOMENTUM_WINDOWS.items():
        recent_start = now - timedelta(days=days)
        older_start = now - timedelta(days=days * 2)

        recent_count = sum(
            1 for r in collection.reviews if r.timestamp >= recent_start
        )
        older_count = sum(
            1 for r in collection.reviews if older_start <= r.timestamp < recent_start
        )

        if older_count > 0:
            velocity = (recent_count - older_count) / older_count
            velocities.append(velocity)
        elif recent_count > 0:
            velocities.append(1.0)  # Growth from zero

    if not velocities:
        return 0.5

    avg_velocity = sum(velocities) / len(velocities)
    # Map to [0, 1]
    return max(0.0, min(1.0, 0.5 + avg_velocity * 0.25))


def _breakout_detection(collection: ReviewCollection, now: datetime) -> float:
    """Z-score anomaly detection against trailing baseline.

    If current metrics are statistically unusual compared to the
    trailing 90-day baseline, this signals a breakout event.

    Positive breakout → score > 0.5 (sentiment spike)
    Negative breakout → score < 0.5 (sentiment crash)
    No breakout → 0.5
    """
    lookback_start = now - timedelta(days=BREAKOUT_LOOKBACK_DAYS)
    recent_window = now - timedelta(days=7)

    baseline_sentiments = [
        r.sentiment_compound
        for r in collection.reviews
        if r.sentiment_compound is not None and lookback_start <= r.timestamp < recent_window
    ]
    recent_sentiments = [
        r.sentiment_compound
        for r in collection.reviews
        if r.sentiment_compound is not None and r.timestamp >= recent_window
    ]

    if len(baseline_sentiments) < 10 or not recent_sentiments:
        return 0.5  # Insufficient data

    baseline_arr = np.array(baseline_sentiments)
    baseline_mean = float(np.mean(baseline_arr))
    baseline_std = float(np.std(baseline_arr))

    if baseline_std < 0.01:
        baseline_std = 0.01  # Avoid division by zero

    recent_mean = sum(recent_sentiments) / len(recent_sentiments)
    z_score = (recent_mean - baseline_mean) / baseline_std

    # Check volume breakout too
    baseline_daily_vol = len(baseline_sentiments) / max(1, BREAKOUT_LOOKBACK_DAYS - 7)
    recent_daily_vol = len(recent_sentiments) / 7

    vol_z = 0.0
    if baseline_daily_vol > 0:
        vol_z = (recent_daily_vol - baseline_daily_vol) / max(0.1, baseline_daily_vol)

    # Combined breakout score
    # Sentiment breakout is primary, volume breakout amplifies it
    if abs(z_score) >= BREAKOUT_ZSCORE_THRESHOLD:
        # Significant breakout detected
        direction = 1.0 if z_score > 0 else -1.0
        magnitude = min(1.0, abs(z_score) / 4.0)  # Cap at z=4
        vol_amplifier = 1.0 + min(0.3, max(0, vol_z * 0.1))
        breakout_signal = direction * magnitude * vol_amplifier
    else:
        breakout_signal = 0.0

    # Map to [0, 1]
    return max(0.0, min(1.0, 0.5 + breakout_signal * 0.5))


def _build_explanation(components: dict[str, float]) -> str:
    parts: list[str] = []

    sv = components["sentiment_velocity"]
    if sv > 0.65:
        parts.append("Sentiment trending UP")
    elif sv < 0.35:
        parts.append("Sentiment trending DOWN")
    else:
        parts.append("Sentiment stable")

    vv = components["volume_velocity"]
    if vv > 0.65:
        parts.append("Volume increasing")
    elif vv < 0.35:
        parts.append("Volume declining")
    else:
        parts.append("Volume stable")

    bd = components["breakout_detection"]
    if bd > 0.75:
        parts.append("POSITIVE breakout detected")
    elif bd < 0.25:
        parts.append("NEGATIVE breakout detected")
    else:
        parts.append("No breakout")

    return "; ".join(parts)
