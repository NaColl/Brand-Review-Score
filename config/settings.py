"""
Brand Sentiment Score (BSS) — Configuration & Scoring Weights

The BSS is built on the "Sentiment Iceberg" model:

    ┌─────────────────────────────────┐
    │  SURFACE: Review Quality (RQS)  │  ← What customers explicitly say
    ├─────────────────────────────────┤
    │  CURRENT: Social Sentiment (SSS)│  ← Where the conversation is going
    ├─────────────────────────────────┤
    │  MOMENTUM: Sentiment Delta (MS) │  ← Rate of change (most predictive)
    ├─────────────────────────────────┤
    │  DEEP: Brand Health (BHI)       │  ← Structural loyalty indicators
    ├─────────────────────────────────┤
    │  FLOOR: Competitive Position    │  ← Relative standing vs peers
    └─────────────────────────────────┘

Academic basis:
- Momentum weighted highest per Bollen et al. (2011), Tetlock (2007)
- Negativity bias (2.5x) per Baumeister et al. (2001), Rozin & Royzman (2001)
- Volume changes > absolute levels per Tirunillai & Tellis (2012)
"""

import os
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Dimension weights — sum to 1.0
# ---------------------------------------------------------------------------
DIMENSION_WEIGHTS = {
    "review_quality": 0.25,       # RQS: surface-level review signals
    "social_sentiment": 0.20,     # SSS: social + news conversation
    "momentum": 0.25,             # MS:  rate-of-change (highest predictive power)
    "brand_health": 0.15,         # BHI: deep structural loyalty
    "competitive_position": 0.15, # CPS: relative to competitors
}

# ---------------------------------------------------------------------------
# Sub-dimension weights (within each dimension)
# ---------------------------------------------------------------------------

# Dimension 1 — Review Quality Score
RQS_WEIGHTS = {
    "normalized_rating": 0.40,         # Time-decay weighted star average
    "review_volume_health": 0.25,      # Volume relative to category + growth
    "review_depth": 0.20,              # Average review length / detail
    "sentiment_distribution": 0.15,    # Shape of rating distribution
}

# Dimension 2 — Social Sentiment Score
SSS_WEIGHTS = {
    "reddit_sentiment": 0.40,          # Reddit discussion tone
    "news_sentiment": 0.40,            # Google News headline sentiment
    "search_interest": 0.20,           # Google Trends normalized interest
}

# Dimension 3 — Momentum Score
MS_WEIGHTS = {
    "sentiment_velocity": 0.40,        # d(sentiment)/dt
    "volume_velocity": 0.30,           # d(volume)/dt
    "breakout_detection": 0.30,        # Z-score anomaly detection
}

# Dimension 4 — Brand Health Indicators
BHI_WEIGHTS = {
    "nps_proxy": 0.50,                 # Net Promoter Score from text
    "response_quality": 0.25,          # Brand response rate + quality
    "loyalty_signals": 0.25,           # Repeat customer language
}

# Dimension 5 — Competitive Position Score
CPS_WEIGHTS = {
    "relative_rating": 0.40,           # Rating vs category average
    "share_of_voice": 0.30,            # % of category mentions
    "sentiment_gap": 0.30,             # Sentiment advantage vs competitor
}

# ---------------------------------------------------------------------------
# Sentiment analysis parameters
# ---------------------------------------------------------------------------
NEGATIVITY_BIAS_MULTIPLIER = 2.5  # Negative sentiment has 2.5x impact
RECENCY_DECAY_LAMBDA = 0.01       # Exponential decay: exp(-λ * days_ago)
RECENCY_HALF_LIFE_DAYS = 69       # ln(2) / 0.01 ≈ 69 days

# Breakout detection
BREAKOUT_ZSCORE_THRESHOLD = 2.0   # |Z| > 2 is significant
BREAKOUT_LOOKBACK_DAYS = 90       # Rolling window for baseline

# Momentum windows
MOMENTUM_WINDOWS = {
    "short": 7,    # 7-day window
    "medium": 14,  # 14-day window
    "long": 30,    # 30-day window
}

# ---------------------------------------------------------------------------
# Predictive signal thresholds
# ---------------------------------------------------------------------------
SIGNAL_THRESHOLDS = {
    "strong_bullish": 8.0,    # BSS delta > +8 over 30 days
    "moderate_bullish": 3.0,  # BSS delta > +3
    "neutral_upper": 3.0,     # |BSS delta| <= 3
    "moderate_bearish": -3.0, # BSS delta < -3
    "strong_bearish": -8.0,   # BSS delta < -8
}

# Sentiment-Price Divergence (for public companies)
DIVERGENCE_THRESHOLD = 0.15  # 15% divergence triggers signal

# ---------------------------------------------------------------------------
# NLP engine selection
# ---------------------------------------------------------------------------
NLP_ENGINE_PRIORITY = [
    "vader",       # Fast, rule-based — always available
    "textblob",    # Pattern-based fallback
    "finbert",     # Financial domain (optional, needs transformers)
]

# NPS Proxy keyword sets
NPS_PROMOTER_PHRASES = [
    "highly recommend", "would recommend", "love this", "love their",
    "best brand", "best company", "amazing service", "fantastic",
    "five stars", "5 stars", "exceeded expectations", "loyal customer",
    "will buy again", "always come back", "never disappointed",
    "top notch", "world class", "can't recommend enough",
]

NPS_DETRACTOR_PHRASES = [
    "would not recommend", "do not recommend", "avoid", "stay away",
    "terrible", "horrible", "worst", "never again", "never buy",
    "waste of money", "rip off", "scam", "fraud", "disgusting",
    "unacceptable", "deal breaker", "lost my business", "filing complaint",
]

# ---------------------------------------------------------------------------
# Data collection settings
# ---------------------------------------------------------------------------
@dataclass
class CollectorConfig:
    """Configuration for data collectors."""

    # Reddit
    reddit_client_id: str = field(
        default_factory=lambda: os.environ.get("REDDIT_CLIENT_ID", "")
    )
    reddit_client_secret: str = field(
        default_factory=lambda: os.environ.get("REDDIT_CLIENT_SECRET", "")
    )
    reddit_user_agent: str = "BrandSentimentScore/1.0"
    reddit_subreddits: list[str] = field(
        default_factory=lambda: [
            "stocks", "investing", "wallstreetbets", "technology",
            "business", "personalfinance", "consumer",
        ]
    )
    reddit_post_limit: int = 100

    # Google News RSS
    google_news_max_articles: int = 50
    google_news_language: str = "en"
    google_news_country: str = "US"

    # Google Trends
    google_trends_timeframe: str = "today 3-m"
    google_trends_geo: str = "US"

    # Wikipedia
    wikipedia_project: str = "en.wikipedia"
    wikipedia_lookback_days: int = 90

    # Financial (yfinance)
    financial_lookback_period: str = "6mo"

    # General
    request_timeout: int = 30
    max_retries: int = 3
    retry_backoff: float = 2.0


DEFAULT_CONFIG = CollectorConfig()
