"""
Brand Sentiment Score (BSS) v2 — Configuration & Scoring Weights

UNIFIED 8-DIMENSION MODEL ("Sentiment Iceberg" v2)

    ┌───────────────────────────────────────┐
    │  1. DISCOVERABILITY                   │  ← Can people find the brand?
    ├───────────────────────────────────────┤
    │  2. IDENTITY                          │  ← Do people align with its values?
    ├───────────────────────────────────────┤
    │  3. VALUE PERCEPTION                  │  ← Is price fair for quality?
    ├───────────────────────────────────────┤
    │  4. CONNECTION                        │  ← Do people engage emotionally?
    ├───────────────────────────────────────┤
    │  5. LOVE                              │  ← Do people advocate for it?
    ├───────────────────────────────────────┤
    │  6. MOMENTUM (most predictive)        │  ← Rate of change in sentiment
    ├───────────────────────────────────────┤
    │  7. COMPETITIVE POSITION              │  ← Standing vs peers
    ├───────────────────────────────────────┤
    │  8. PRICING INTELLIGENCE              │  ← Sale %, resale, discount depth
    └───────────────────────────────────────┘

    SEPARATE: Hype vs Health Index (HHI)
    ← 2-axis chart: buzz vs financial/operational health

Academic basis:
- Momentum weighted highest per Bollen et al. (2011), Tetlock (2007)
- Negativity bias (2.5x) per Baumeister et al. (2001), Rozin & Royzman (2001)
- Volume changes > absolute levels per Tirunillai & Tellis (2012)
- Resale premium as brand equity proxy per Keller (1993), Aaker (1991)
"""

import os
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════════════════
# DIMENSION WEIGHTS — sum to 1.0
# ═══════════════════════════════════════════════════════════════════════════

# --- Default profile (all brands) ---
DIMENSION_WEIGHTS = {
    "discoverability": 0.12,
    "identity": 0.08,
    "value_perception": 0.15,
    "connection": 0.10,
    "love": 0.10,
    "momentum": 0.20,             # Highest — most predictive per literature
    "competitive_position": 0.10,
    "pricing_intelligence": 0.15,
}

# --- Luxury brand profile ---
# Resale premium, identity, and love matter more for luxury brands.
# Discoverability matters less (luxury thrives on exclusivity).
LUXURY_DIMENSION_WEIGHTS = {
    "discoverability": 0.07,      # Lower — luxury is about exclusivity
    "identity": 0.12,             # Higher — brand DNA is everything
    "value_perception": 0.12,     # Includes resale premium
    "connection": 0.10,
    "love": 0.14,                 # Higher — emotional attachment drives luxury
    "momentum": 0.18,             # Still high — trend changes predict stock
    "competitive_position": 0.08,
    "pricing_intelligence": 0.19, # Highest — resale value IS luxury equity
}


# ═══════════════════════════════════════════════════════════════════════════
# SUB-DIMENSION WEIGHTS (within each dimension)
# ═══════════════════════════════════════════════════════════════════════════

# Dimension 1 — Discoverability
DISC_WEIGHTS = {
    "search_volume": 0.30,            # Google Trends absolute interest
    "search_trend": 0.20,             # Google Trends direction (rising/falling)
    "news_volume": 0.20,              # Number of news articles
    "social_reach": 0.15,             # Reddit mention volume + engagement
    "wikipedia_interest": 0.15,       # Wikipedia pageview level
}

# Dimension 2 — Identity
IDENT_WEIGHTS = {
    "narrative_sentiment": 0.35,      # Are earned media narratives positive?
    "values_alignment": 0.35,         # Does text align with stated brand values?
    "consistency": 0.30,              # Is messaging consistent over time?
}

# Dimension 3 — Value Perception
VALUE_WEIGHTS = {
    "review_rating": 0.30,            # Time-decay weighted star average
    "price_quality_sentiment": 0.25,  # "worth it" / "overpriced" language
    "review_depth": 0.15,             # Review detail as quality proxy
    "resale_premium": 0.30,           # Resale value vs retail (luxury signal)
}

# Dimension 4 — Connection
CONN_WEIGHTS = {
    "engagement_rate": 0.40,          # Upvotes, comments, shares per mention
    "emotional_tone": 0.30,           # Intensity of emotional language
    "community_growth": 0.30,         # Volume trend of engaged mentions
}

# Dimension 5 — Love
LOVE_WEIGHTS = {
    "nps_proxy": 0.35,                # Net Promoter Score from text
    "loyalty_signals": 0.25,          # "been using for years", repeat language
    "advocacy_intensity": 0.25,       # Strength of positive recommendations
    "emotional_attachment": 0.15,     # "can't live without", "obsessed" language
}

# Dimension 6 — Momentum (unchanged from v1)
MS_WEIGHTS = {
    "sentiment_velocity": 0.40,       # d(sentiment)/dt
    "volume_velocity": 0.30,          # d(volume)/dt
    "breakout_detection": 0.30,       # Z-score anomaly detection
}

# Dimension 7 — Competitive Position (unchanged from v1)
CPS_WEIGHTS = {
    "relative_rating": 0.40,          # Rating vs category average
    "share_of_voice": 0.30,           # % of category mentions
    "sentiment_gap": 0.30,            # Sentiment advantage vs competitor
}

# Dimension 8 — Pricing Intelligence
PRICING_WEIGHTS = {
    "sale_percentage": 0.30,          # % of collection on sale (brand heat)
    "discount_depth": 0.20,           # Average discount % (desperation signal)
    "resale_value_ratio": 0.30,       # Resale price / retail price
    "price_sentiment": 0.20,          # "expensive"/"deal" language in reviews
}

# ═══════════════════════════════════════════════════════════════════════════
# HYPE VS HEALTH INDEX (separate top-level metric)
# ═══════════════════════════════════════════════════════════════════════════

HHI_WEIGHTS = {
    "hype": {
        "google_trends": 0.35,        # Search interest
        "social_volume": 0.30,        # Reddit/news mention volume
        "wikipedia_pageviews": 0.20,  # Public attention proxy
        "news_volume": 0.15,          # Press coverage volume
    },
    "health": {
        "stock_momentum": 0.25,       # Price trend (public companies)
        "financials": 0.25,           # Revenue/margin signals
        "low_sale_pct": 0.25,         # Low sale % = healthy demand
        "resale_premium": 0.25,       # High resale = strong brand equity
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# LUXURY BRAND CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

LUXURY_BRANDS = {
    # Tier 1: Ultra-luxury
    "hermes", "chanel", "louis vuitton", "dior", "brunello cucinelli",
    "loro piana", "graff", "patek philippe", "richard mille", "rolls-royce",
    # Tier 2: Luxury
    "gucci", "prada", "saint laurent", "bottega veneta", "balenciaga",
    "celine", "valentino", "givenchy", "fendi", "burberry", "versace",
    "cartier", "tiffany", "rolex", "omega", "tag heuer",
    # Tier 3: Accessible luxury
    "coach", "michael kors", "kate spade", "ralph lauren", "tommy hilfiger",
    "hugo boss", "calvin klein", "armani", "max mara", "moncler",
    "canada goose", "golden goose", "off-white",
}

# Luxury-specific keyword sets
LUXURY_ASPIRATIONAL_PHRASES = [
    "dream brand", "grail", "holy grail", "bucket list", "aspirational",
    "investment piece", "timeless", "heirloom", "forever piece",
    "iconic", "heritage", "craftmanship", "craftsmanship", "artisan",
    "made in italy", "made in france", "swiss made", "handmade",
    "limited edition", "exclusive", "rare", "collectible",
]

LUXURY_DEVALUATION_PHRASES = [
    "cheapened", "mass market", "lost its exclusivity", "overexposed",
    "ubiquitous", "too common", "not special anymore", "sold out",
    "outlet", "discount rack", "fast fashion", "knock off", "knockoff",
    "fake", "counterfeit", "not worth the price", "overpriced for what it is",
]

# Resale platforms for data collection
RESALE_PLATFORMS = {
    "therealreal": {
        "base_url": "https://www.therealreal.com",
        "search_path": "/shop?q={query}",
    },
    "vestiaire": {
        "base_url": "https://www.vestiairecollective.com",
        "search_path": "/search/?q={query}",
    },
    "stockx": {
        "base_url": "https://stockx.com",
        "search_path": "/search?s={query}",
    },
    "grailed": {
        "base_url": "https://www.grailed.com",
        "search_path": "/shop?query={query}",
    },
}

# Brand values keywords for Identity dimension
BRAND_VALUES_KEYWORDS = {
    "sustainability": [
        "sustainable", "sustainability", "eco-friendly", "green", "recycled",
        "organic", "carbon neutral", "carbon footprint", "ethical", "fair trade",
        "circular", "biodegradable", "renewable", "zero waste", "planet",
    ],
    "innovation": [
        "innovative", "innovation", "cutting edge", "revolutionary", "disruptive",
        "technology", "tech-forward", "futuristic", "breakthrough", "pioneering",
    ],
    "inclusivity": [
        "inclusive", "diversity", "diverse", "representation", "accessible",
        "for everyone", "all sizes", "all genders", "body positive",
    ],
    "craftsmanship": [
        "handmade", "artisan", "crafted", "bespoke", "handcrafted",
        "attention to detail", "quality materials", "precision", "heritage",
    ],
    "community": [
        "community", "belonging", "tribe", "family", "together",
        "movement", "culture", "lifestyle", "authentic",
    ],
}

# ═══════════════════════════════════════════════════════════════════════════
# SENTIMENT ANALYSIS PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════
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

# ═══════════════════════════════════════════════════════════════════════════
# PREDICTIVE SIGNALS
# ═══════════════════════════════════════════════════════════════════════════
SIGNAL_THRESHOLDS = {
    "strong_bullish": 8.0,
    "moderate_bullish": 3.0,
    "neutral_upper": 3.0,
    "moderate_bearish": -3.0,
    "strong_bearish": -8.0,
}

DIVERGENCE_THRESHOLD = 0.15

# ═══════════════════════════════════════════════════════════════════════════
# NLP
# ═══════════════════════════════════════════════════════════════════════════
NLP_ENGINE_PRIORITY = ["vader", "textblob", "finbert"]

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

# Emotional attachment keywords (for Love dimension)
EMOTIONAL_ATTACHMENT_PHRASES = [
    "obsessed", "can't live without", "addicted", "in love with",
    "my favorite", "ride or die", "die for", "absolute favorite",
    "nothing compares", "nothing else comes close", "changed my life",
    "part of my identity", "cult following", "stan",
]

# Price-quality sentiment keywords (for Value Perception)
PRICE_POSITIVE_PHRASES = [
    "worth every penny", "worth the price", "good value", "great deal",
    "you get what you pay for", "worth the investment", "fair price",
    "bang for buck", "bang for your buck", "reasonably priced",
    "investment piece", "holds its value", "pays for itself",
]

PRICE_NEGATIVE_PHRASES = [
    "overpriced", "too expensive", "not worth", "rip off", "ripoff",
    "waste of money", "highway robbery", "outrageous price",
    "can't justify the price", "better options for less",
    "price keeps going up", "used to be affordable", "priced out",
]

# Engagement intensity keywords (for Connection dimension)
HIGH_ENGAGEMENT_PHRASES = [
    "just had to share", "everyone needs to know", "can't stop talking about",
    "changed my mind about", "converted me", "made me a believer",
    "blew my mind", "game changer", "game-changer",
]

# Legacy v1 weights (kept for backward compatibility)
RQS_WEIGHTS = {
    "normalized_rating": 0.40,
    "review_volume_health": 0.25,
    "review_depth": 0.20,
    "sentiment_distribution": 0.15,
}
SSS_WEIGHTS = {
    "reddit_sentiment": 0.40,
    "news_sentiment": 0.40,
    "search_interest": 0.20,
}
BHI_WEIGHTS = {
    "nps_proxy": 0.50,
    "response_quality": 0.25,
    "loyalty_signals": 0.25,
}

# ═══════════════════════════════════════════════════════════════════════════
# DATA COLLECTION SETTINGS
# ═══════════════════════════════════════════════════════════════════════════

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
    reddit_user_agent: str = "BrandSentimentScore/2.0"
    reddit_subreddits: list[str] = field(
        default_factory=lambda: [
            "stocks", "investing", "wallstreetbets", "technology",
            "business", "personalfinance", "consumer",
            "fashion", "femalefashionadvice", "malefashionadvice",
            "luxury", "streetwear", "sneakers",
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

    # Resale / Pricing
    resale_max_items: int = 50
    pricing_max_items: int = 50

    # General
    request_timeout: int = 30
    max_retries: int = 3
    retry_backoff: float = 2.0


DEFAULT_CONFIG = CollectorConfig()
