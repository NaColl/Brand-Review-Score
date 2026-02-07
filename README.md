# Brand Sentiment Score (BSS)

**A multi-dimensional scoring engine that predicts brand popularity and stock price movements from free public data sources.**

Built on the **"Sentiment Iceberg" model** — most brand scores only measure the surface (star ratings). BSS captures five layers of brand intelligence, from visible review quality down to competitive positioning and momentum signals.

## The Scoring Framework

```
BSS (0-100)
│
├── 25%  Review Quality (RQS)        ← What customers explicitly say
│        ├── Normalized Rating (40%)
│        ├── Review Volume Health (25%)
│        ├── Review Depth (20%)
│        └── Sentiment Distribution (15%)
│
├── 20%  Social Sentiment (SSS)      ← Where the conversation is going
│        ├── Reddit Sentiment (40%)
│        ├── News Sentiment (40%)
│        └── Search Interest (20%)
│
├── 25%  Momentum (MS)               ← Rate of change (MOST PREDICTIVE)
│        ├── Sentiment Velocity (40%)
│        ├── Volume Velocity (30%)
│        └── Breakout Detection (30%)
│
├── 15%  Brand Health (BHI)          ← Structural loyalty indicators
│        ├── NPS Proxy (50%)
│        ├── Response Quality (25%)
│        └── Loyalty Signals (25%)
│
└── 15%  Competitive Position (CPS)  ← Relative standing vs peers
         ├── Relative Rating (40%)
         ├── Share of Voice (30%)
         └── Sentiment Gap (30%)
```

### Why Momentum Gets the Highest Weight

Academic research consistently shows that **changes in sentiment are more predictive than absolute levels**:

- **Bollen et al. (2011)**: Twitter mood predicts DJIA with 87.6% accuracy
- **Tetlock (2007)**: Media pessimism predicts downward pressure on stock prices
- **Tirunillai & Tellis (2012)**: Volume changes predict abnormal stock returns
- **Fornell et al.**: ACSI changes lead stock price changes by 1-3 months

A brand with a 3.5/5 rating **trending up** is more bullish than one at 4.5/5 **trending down**.

## Free Data Sources

| Source | Data | Cost | Python Library |
|--------|------|------|----------------|
| Google News RSS | Headlines, sentiment | Free | `feedparser` |
| Reddit (PRAW) | Posts, comments, votes | Free (60 req/min) | `praw` |
| Google Trends | Search interest over time | Free | `pytrends` |
| Wikipedia Pageviews | Brand awareness proxy | Free | `requests` |
| Yahoo Finance | Stock prices, fundamentals | Free | `yfinance` |

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

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Score a single brand
python cli.py score --brand "Tesla" --ticker TSLA

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
src/
├── models/          # Data models (Brand, Review, Score, Signal)
├── collectors/      # Data source integrations (5 free sources)
├── analysis/        # NLP sentiment pipeline (VADER/TextBlob/FinBERT)
├── scoring/         # Five scoring dimensions + composite calculator
├── prediction/      # Trend detection + signal generation
└── reporting/       # Console output (Rich) + JSON/CSV export
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
