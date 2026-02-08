# Brand Sentiment Score (BSS) — SaaS Platform

**AI-powered brand intelligence SaaS. Track brand sentiment, predict stock movements, and benchmark competitors — from free public data.**

Production-ready REST API + web dashboard + automated scoring. Deployable via Docker in one command.

## Deploy in 60 Seconds

```bash
# Docker (production)
docker compose up -d
# Open http://localhost:8000

# Local development
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

Then visit `http://localhost:8000` and click **Quick Demo** to auto-setup 4 brands with scores.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/keys` | Create API key (no auth needed) |
| `POST` | `/api/v1/brands` | Register a brand to track |
| `GET` | `/api/v1/brands` | List all tracked brands |
| `POST` | `/api/v1/brands/{id}/score` | Score a brand (live data) |
| `POST` | `/api/v1/brands/{id}/demo-score` | Score with demo data (offline) |
| `GET` | `/api/v1/brands/{id}/scores` | Historical score timeline |
| `GET` | `/api/v1/brands/{id}/latest` | Latest score |
| `GET` | `/api/v1/compare?brand_ids=1,2,3` | Compare brands side-by-side |
| `GET` | `/api/v1/alerts` | Score change alerts |
| `GET` | `/api/v1/dashboard` | Aggregated dashboard data |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Interactive API docs (Swagger) |

### Authentication

Every request (except `/api/v1/keys`, `/health`, `/docs`) requires an `X-API-Key` header.

```bash
# Create a key
curl -X POST http://localhost:8000/api/v1/keys \
  -H "Content-Type: application/json" \
  -d '{"name": "My Company", "tier": "pro"}'

# Use it
curl http://localhost:8000/api/v1/brands \
  -H "X-API-Key: bss_..."
```

### Tiers

| Tier | Rate Limit | Brands | Price |
|------|-----------|--------|-------|
| Starter | 100 req/day | 10 | Free |
| Pro | 1,000 req/day | 50 | $499/mo |
| Enterprise | 10,000 req/day | 500 | $2,499/mo |

## The Scoring Engine

Built on the **"Sentiment Iceberg" v2 model** — a unified 8-dimension framework with a separate Hype vs Health Index and Luxury Brand Index.

## The Scoring Framework (v2 — Unified 8 Dimensions)

```
BSS (0-100)
│
├── 12%  Discoverability                ← Can people find the brand?
│        ├── Search Volume (30%)
│        ├── Search Trend (20%)
│        ├── News Volume (20%)
│        ├── Social Reach (15%)
│        └── Wikipedia Interest (15%)
│
├──  8%  Identity                       ← Do people align with brand values?
│        ├── Narrative Sentiment (35%)
│        ├── Values Alignment (35%)
│        └── Consistency (30%)
│
├── 15%  Value Perception               ← Is price fair for quality?
│        ├── Review Rating (30%)
│        ├── Price-Quality Sentiment (25%)
│        ├── Review Depth (15%)
│        └── Resale Premium (30%)
│
├── 10%  Connection                     ← Do people engage emotionally?
│        ├── Engagement Rate (40%)
│        ├── Emotional Tone (30%)
│        └── Community Growth (30%)
│
├── 10%  Love                           ← Do people advocate for it?
│        ├── NPS Proxy (35%)
│        ├── Loyalty Signals (25%)
│        ├── Advocacy Intensity (25%)
│        └── Emotional Attachment (15%)
│
├── 20%  Momentum (MOST PREDICTIVE)     ← Rate of change in sentiment
│        ├── Sentiment Velocity (40%)
│        ├── Volume Velocity (30%)
│        └── Breakout Detection (30%)
│
├── 10%  Competitive Position           ← Standing vs peers
│        ├── Relative Rating (40%)
│        ├── Share of Voice (30%)
│        └── Sentiment Gap (30%)
│
└── 15%  Pricing Intelligence           ← Sale %, resale, discount depth
         ├── Sale Percentage (30%)
         ├── Discount Depth (20%)
         ├── Resale Value Ratio (30%)
         └── Price Sentiment (20%)
```

### Luxury Brand Weighting Profile

Luxury brands are auto-detected (40+ brands across 3 tiers) and scored with a different weight profile that emphasizes pricing intelligence (19%), momentum (18%), love (14%), and identity (12%) while de-weighting discoverability (7%) — because luxury thrives on exclusivity, not ubiquity.

### Why Momentum Gets the Highest Weight

Academic research consistently shows that **changes in sentiment are more predictive than absolute levels**:

- **Bollen et al. (2011)**: Twitter mood predicts DJIA with 87.6% accuracy
- **Tetlock (2007)**: Media pessimism predicts downward pressure on stock prices
- **Tirunillai & Tellis (2012)**: Volume changes predict abnormal stock returns
- **Fornell et al.**: ACSI changes lead stock price changes by 1-3 months

A brand with a 3.5/5 rating **trending up** is more bullish than one at 4.5/5 **trending down**.

## Hype vs Health Index (HHI)

A separate 2-axis metric that maps brands on a buzz vs. fundamentals chart:

```
                    High Health
                        │
    Hidden Gem          │          Strong Brand
    (Low Hype,          │          (High Hype,
     High Health)       │           High Health)
                        │
  ──────────────────────┼──────────────────────
                        │
    Declining           │          Overhyped
    (Low Hype,          │          (High Hype,
     Low Health)        │           Low Health)
                        │
                    Low Health
```

**Hype axis:** Google Trends (35%), social volume (30%), Wikipedia pageviews (20%), news volume (15%)
**Health axis:** Stock momentum (25%), financials (25%), low sale % (25%), resale premium (25%)

## Luxury Brand Index

For auto-detected luxury brands, an additional sub-metric tracks:

| Component | Weight | Signal |
|-----------|--------|--------|
| Resale Premium Ratio | 25% | >1.0 = appreciating asset |
| Exclusivity Score | 25% | Limited edition / rare language |
| Aspirational Score | 35% | "Dream brand" / "grail" language |
| Heritage Score | 15% | "Heritage" / "since" / "tradition" |

## Free Data Sources

| Source | Data | Cost | Python Library |
|--------|------|------|----------------|
| Google News RSS | Headlines, sentiment | Free | `atoma` |
| Reddit (PRAW) | Posts, comments, votes | Free (60 req/min) | `praw` |
| Google Trends | Search interest over time | Free | `pytrends` |
| Wikipedia Pageviews | Brand awareness proxy | Free | `requests` |
| Yahoo Finance | Stock prices, fundamentals | Free | `yfinance` |
| Resale Platforms | TheRealReal, Vestiaire, StockX, Grailed | Free (scrape) | `requests` |

## Predictive Signals

### BSS Momentum Signal

| BSS Delta (30d) | Signal | Interpretation |
|-----------------|--------|----------------|
| > +8 | **Strong Bullish** | Rapid sentiment improvement |
| +3 to +8 | Moderate Bullish | Sentiment improving |
| -3 to +3 | Neutral | Stable |
| -8 to -3 | Moderate Bearish | Sentiment declining |
| < -8 | **Strong Bearish** | Rapid deterioration |

### Sentiment-Price Divergence (Public Companies)

When BSS trend and stock price trend diverge, this signals potential mis-pricing:

- **BSS rising + Price flat/falling** → Potential undervaluation
- **BSS falling + Price rising** → Potential overvaluation

### Pricing Intelligence Signals

- **>40% of collection on sale** → Brand heat dying (bearish)
- **Resale ratio >1.0** → Appreciating asset (strong luxury equity)
- **Deep discounts (>50% off)** → Desperation / overstock

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Score a single brand
python cli.py score --brand "Tesla" --ticker TSLA

# Score a luxury brand (auto-detected)
python cli.py score --brand "Gucci"

# Force luxury scoring profile
python cli.py score --brand "MyBrand" --luxury

# Provide pricing data
python cli.py score --brand "Gucci" --sale-pct 0.3 --discount-pct 0.25 --resale-ratio 0.85

# Compare brands
python cli.py compare --brands "Tesla,Ford,Rivian"

# Export to JSON
python cli.py export --brand "Nike" --ticker NKE --format json --output report.json

# Use ensemble sentiment engine
python cli.py score --brand "Apple" --ticker AAPL --engine ensemble
```

### Configuration

Copy `config/brands_example.yaml` to `config/brands.yaml` and customize:

```yaml
brands:
  - name: "Your Brand"
    ticker: "TICK"
    wikipedia_article: "Your_Brand"
    search_terms: ["Your Brand", "Brand Inc"]
    subreddits: ["yourbrand"]
    competitors: ["Competitor A", "Competitor B"]
    category: "industry"
```

### Environment Variables

For Reddit data collection (optional):

```bash
export REDDIT_CLIENT_ID="your_client_id"
export REDDIT_CLIENT_SECRET="your_client_secret"
```

## Architecture

```
├── server.py              # FastAPI REST API (production entry point)
├── cli.py                 # CLI tool (score, compare, demo, export)
├── Dockerfile             # Production container
├── docker-compose.yml     # One-command deployment
├── dashboard/
│   └── index.html         # Web dashboard (Tailwind + Chart.js SPA)
└── src/
    ├── database.py        # SQLite persistence (brands, scores, alerts, API keys)
    ├── auth.py            # API key authentication middleware
    ├── scheduler.py       # APScheduler for automated scoring
    ├── demo.py            # Realistic demo data (Nike, Chanel, Tesla, Gap)
    ├── models/            # Data models (Brand, Review, Score, HHI, LBI, Signal)
    ├── collectors/        # Data source integrations
    │   ├── google_news.py       # Google News RSS via atoma
    │   ├── reddit_collector.py  # Reddit via PRAW
    │   ├── google_trends.py     # Google Trends via pytrends
    │   ├── wikipedia.py         # Wikipedia pageviews API
    │   ├── financial.py         # Yahoo Finance via yfinance
    │   └── resale.py            # TheRealReal, Vestiaire, StockX, Grailed
    ├── analysis/          # NLP sentiment pipeline (VADER/TextBlob/FinBERT)
    ├── scoring/           # 8 scoring dimensions + composite calculator
    │   ├── discoverability.py        # Dim 1
    │   ├── identity.py               # Dim 2
    │   ├── value_perception.py       # Dim 3
    │   ├── connection.py             # Dim 4
    │   ├── love.py                   # Dim 5
    │   ├── momentum.py               # Dim 6
    │   ├── competitive.py            # Dim 7
    │   ├── pricing_intelligence.py   # Dim 8
    │   ├── hype_health.py            # HHI (separate metric)
    │   └── composite.py              # Orchestrator
    ├── prediction/        # Trend detection + signal generation
    └── reporting/         # Console output (Rich) + JSON/CSV export
```

## NLP Engines

| Engine | Speed | Accuracy | Best For |
|--------|-------|----------|----------|
| VADER | Fastest | Good | Social media, short text |
| TextBlob | Fast | Moderate | General reviews |
| FinBERT | Slow | Highest | Financial news (requires `transformers`) |

Install FinBERT support: `pip install transformers torch`

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

## Grading Scale

| Score | Grade | Meaning |
|-------|-------|---------|
| 90-100 | A+ | Exceptional brand sentiment |
| 80-89 | A | Strong positive sentiment |
| 70-79 | B+ | Above average |
| 60-69 | B | Healthy / average |
| 50-59 | C | Below average — monitor |
| 40-49 | D | Weak — likely declining |
| 0-39 | F | Critical — active brand damage |
