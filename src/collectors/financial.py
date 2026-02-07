"""Financial data collector via yfinance — completely free."""

from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from config.settings import DEFAULT_CONFIG
from src.collectors.base import BaseCollector
from src.models.brand import Brand
from src.models.review import Review, ReviewCollection

logger = logging.getLogger(__name__)


class FinancialCollector(BaseCollector):
    """Collects stock price and financial data for public companies.

    Uses yfinance (unofficial Yahoo Finance scraper) — free, no key.
    Only activates if brand has a ticker symbol.
    """

    name = "financial"

    def __init__(self, config: object | None = None) -> None:
        super().__init__()
        cfg = config or DEFAULT_CONFIG
        self.period = cfg.financial_lookback_period

    def _collect(self, brand: Brand) -> ReviewCollection:
        if not brand.ticker:
            return ReviewCollection(brand_name=brand.name)

        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance not installed — skipping financial data.")
            return ReviewCollection(brand_name=brand.name)

        ticker = yf.Ticker(brand.ticker)
        hist = ticker.history(period=self.period)

        if hist.empty:
            logger.warning("No price data for ticker '%s'", brand.ticker)
            return ReviewCollection(brand_name=brand.name)

        reviews: list[Review] = []
        for date_idx, row in hist.iterrows():
            close = row.get("Close", 0)
            volume = int(row.get("Volume", 0))
            ts = date_idx.to_pydatetime() if isinstance(date_idx, pd.Timestamp) else datetime.utcnow()

            reviews.append(
                Review(
                    text=f"${brand.ticker} close: ${close:.2f}, volume: {volume:,}",
                    source=self.name,
                    timestamp=ts.replace(tzinfo=None),
                    engagement=volume,
                )
            )

        return ReviewCollection(brand_name=brand.name, reviews=reviews)

    def get_price_history(self, brand: Brand) -> pd.DataFrame:
        """Return raw price history DataFrame for correlation analysis."""
        if not brand.ticker:
            return pd.DataFrame()

        try:
            import yfinance as yf
            ticker = yf.Ticker(brand.ticker)
            return ticker.history(period=self.period)
        except Exception as exc:
            logger.warning("Price history fetch failed for '%s': %s", brand.ticker, exc)
            return pd.DataFrame()

    def get_price_change(self, brand: Brand, days: int = 30) -> float | None:
        """Calculate percentage price change over the last N days."""
        hist = self.get_price_history(brand)
        if hist.empty or len(hist) < 2:
            return None

        recent = hist.tail(min(days, len(hist)))
        if len(recent) < 2:
            return None

        start_price = float(recent.iloc[0]["Close"])
        end_price = float(recent.iloc[-1]["Close"])

        if start_price == 0:
            return None

        return ((end_price - start_price) / start_price) * 100
