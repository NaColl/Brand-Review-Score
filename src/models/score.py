"""Score data models — the 8 unified dimensions, composite BSS, and HHI.

v2: Unified 8-Dimension Model + Hype vs Health Index
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


# ═══════════════════════════════════════════════════════════════════════════
# Base dimension
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class DimensionScore:
    """A single scoring dimension result."""

    name: str = ""
    value: float = 0.0         # 0–100 scale
    components: dict[str, float] = field(default_factory=dict)
    explanation: str = ""

    def __post_init__(self) -> None:
        self.value = max(0.0, min(100.0, self.value))


# ═══════════════════════════════════════════════════════════════════════════
# 8 unified dimensions
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class DiscoverabilityScore(DimensionScore):
    """Dim 1 — How easily can people find the brand?"""
    name: str = "Discoverability"


@dataclass
class IdentityScore(DimensionScore):
    """Dim 2 — Do people understand and align with brand values?"""
    name: str = "Identity"


@dataclass
class ValuePerceptionScore(DimensionScore):
    """Dim 3 — Do people perceive price as fair relative to quality?"""
    name: str = "Value Perception"


@dataclass
class ConnectionScore(DimensionScore):
    """Dim 4 — Do people engage and resonate emotionally?"""
    name: str = "Connection"


@dataclass
class LoveScore(DimensionScore):
    """Dim 5 — Do people feel emotionally attached and advocate?"""
    name: str = "Love"


@dataclass
class MomentumScore(DimensionScore):
    """Dim 6 — Rate-of-change signals (most predictive)."""
    name: str = "Momentum"


@dataclass
class CompetitivePositionScore(DimensionScore):
    """Dim 7 — Relative standing vs peers."""
    name: str = "Competitive Position"


@dataclass
class PricingIntelligenceScore(DimensionScore):
    """Dim 8 — Sale %, resale value, discount depth."""
    name: str = "Pricing Intelligence"


# Legacy aliases for backward compatibility
ReviewQualityScore = ValuePerceptionScore
SocialSentimentScore = DiscoverabilityScore
BrandHealthScore = LoveScore


# ═══════════════════════════════════════════════════════════════════════════
# Hype vs Health Index (separate top-level metric)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class HypeHealthIndex:
    """The Hype vs Health Index — a separate 2-axis metric.

    Hype:   0–100 (buzz, search interest, social volume)
    Health: 0–100 (financial strength, low sale %, resale premium)

    Interpretation:
      High Hype + High Health  = Strong brand (ideal)
      High Hype + Low Health   = Overhyped / bubble risk
      Low Hype  + High Health  = Hidden gem / undervalued
      Low Hype  + Low Health   = Declining brand
    """

    brand_name: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    hype_score: float = 50.0       # 0–100
    health_score: float = 50.0     # 0–100

    hype_components: dict[str, float] = field(default_factory=dict)
    health_components: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.hype_score = max(0.0, min(100.0, self.hype_score))
        self.health_score = max(0.0, min(100.0, self.health_score))

    @property
    def quadrant(self) -> str:
        if self.hype_score >= 50 and self.health_score >= 50:
            return "strong_brand"
        elif self.hype_score >= 50 and self.health_score < 50:
            return "overhyped"
        elif self.hype_score < 50 and self.health_score >= 50:
            return "hidden_gem"
        else:
            return "declining"

    @property
    def divergence(self) -> float:
        """Divergence between hype and health. Positive = more hype than health."""
        return self.hype_score - self.health_score

    def to_dict(self) -> dict:
        return {
            "brand": self.brand_name,
            "timestamp": self.timestamp.isoformat(),
            "hype_score": round(self.hype_score, 2),
            "health_score": round(self.health_score, 2),
            "quadrant": self.quadrant,
            "divergence": round(self.divergence, 2),
            "hype_components": {k: round(v, 2) for k, v in self.hype_components.items()},
            "health_components": {k: round(v, 2) for k, v in self.health_components.items()},
        }


# ═══════════════════════════════════════════════════════════════════════════
# Luxury Brand Index (sub-metric for luxury brands)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class LuxuryBrandIndex:
    """Luxury-specific brand equity index.

    Tracks metrics that matter specifically for luxury brands:
    - Resale premium ratio (resale price / retail price)
    - Exclusivity signals (limited edition, waiting list language)
    - Aspirational language ratio
    - Brand heritage strength
    """

    brand_name: str = ""
    resale_premium_ratio: float = 0.0   # >1 = appreciating, <1 = depreciating
    exclusivity_score: float = 50.0     # 0–100
    aspirational_score: float = 50.0    # 0–100
    heritage_score: float = 50.0        # 0–100
    composite: float = 50.0             # 0–100 weighted average

    def to_dict(self) -> dict:
        return {
            "brand": self.brand_name,
            "resale_premium_ratio": round(self.resale_premium_ratio, 3),
            "exclusivity_score": round(self.exclusivity_score, 2),
            "aspirational_score": round(self.aspirational_score, 2),
            "heritage_score": round(self.heritage_score, 2),
            "luxury_index": round(self.composite, 2),
        }


# ═══════════════════════════════════════════════════════════════════════════
# Composite BSS
# ═══════════════════════════════════════════════════════════════════════════

ALL_DIMENSION_ATTRS = [
    "discoverability", "identity", "value_perception", "connection",
    "love", "momentum", "competitive_position", "pricing_intelligence",
]

@dataclass
class BrandSentimentScore:
    """The composite Brand Sentiment Score and all its components.

    v2: 8 unified dimensions + HHI + optional Luxury Brand Index.
    """

    brand_name: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Composite
    bss: float = 0.0                # 0–100 composite score

    # 8 Dimensions
    discoverability: DiscoverabilityScore | None = None
    identity: IdentityScore | None = None
    value_perception: ValuePerceptionScore | None = None
    connection: ConnectionScore | None = None
    love: LoveScore | None = None
    momentum: MomentumScore | None = None
    competitive_position: CompetitivePositionScore | None = None
    pricing_intelligence: PricingIntelligenceScore | None = None

    # Separate metrics
    hype_health: HypeHealthIndex | None = None
    luxury_index: LuxuryBrandIndex | None = None

    # Metadata
    is_luxury: bool = False
    data_sources_used: list[str] = field(default_factory=list)
    total_data_points: int = 0
    confidence: float = 0.0        # 0–1; based on data coverage

    # Legacy aliases (backward compatibility with v1 tests)
    @property
    def review_quality(self) -> ValuePerceptionScore | None:
        return self.value_perception

    @property
    def social_sentiment(self) -> DiscoverabilityScore | None:
        return self.discoverability

    @property
    def brand_health(self) -> LoveScore | None:
        return self.love

    def grade(self) -> str:
        """Letter grade derived from BSS."""
        if self.bss >= 90:
            return "A+"
        elif self.bss >= 80:
            return "A"
        elif self.bss >= 70:
            return "B+"
        elif self.bss >= 60:
            return "B"
        elif self.bss >= 50:
            return "C"
        elif self.bss >= 40:
            return "D"
        else:
            return "F"

    def to_dict(self) -> dict:
        dims = {}
        for dim_attr in ALL_DIMENSION_ATTRS:
            dim = getattr(self, dim_attr)
            if dim is not None:
                dims[dim_attr] = {
                    "name": dim.name,
                    "value": round(dim.value, 2),
                    "components": {k: round(v, 2) for k, v in dim.components.items()},
                    "explanation": dim.explanation,
                }

        result = {
            "brand": self.brand_name,
            "timestamp": self.timestamp.isoformat(),
            "bss": round(self.bss, 2),
            "grade": self.grade(),
            "is_luxury": self.is_luxury,
            "dimensions": dims,
            "data_sources_used": self.data_sources_used,
            "total_data_points": self.total_data_points,
            "confidence": round(self.confidence, 2),
        }

        if self.hype_health:
            result["hype_health_index"] = self.hype_health.to_dict()
        if self.luxury_index:
            result["luxury_brand_index"] = self.luxury_index.to_dict()

        return result


# ═══════════════════════════════════════════════════════════════════════════
# Predictive Signal
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class PredictiveSignal:
    """A buy/sell/hold signal derived from BSS trends."""

    brand_name: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    bss_current: float = 0.0
    bss_previous: float = 0.0
    bss_delta: float = 0.0
    signal: Literal[
        "strong_bullish", "moderate_bullish", "neutral",
        "moderate_bearish", "strong_bearish"
    ] = "neutral"

    price_change_pct: float | None = None
    sentiment_price_divergence: float | None = None
    divergence_signal: Literal["undervalued", "overvalued", "aligned"] | None = None

    # HHI-based signal
    hhi_quadrant: str | None = None

    confidence: float = 0.0
    explanation: str = ""

    def to_dict(self) -> dict:
        result = {
            "brand": self.brand_name,
            "timestamp": self.timestamp.isoformat(),
            "bss_current": round(self.bss_current, 2),
            "bss_previous": round(self.bss_previous, 2),
            "bss_delta": round(self.bss_delta, 2),
            "signal": self.signal,
            "confidence": round(self.confidence, 2),
            "explanation": self.explanation,
        }
        if self.price_change_pct is not None:
            result["price_change_pct"] = round(self.price_change_pct, 2)
            result["sentiment_price_divergence"] = (
                round(self.sentiment_price_divergence, 2)
                if self.sentiment_price_divergence is not None
                else None
            )
            result["divergence_signal"] = self.divergence_signal
        if self.hhi_quadrant is not None:
            result["hhi_quadrant"] = self.hhi_quadrant
        return result
