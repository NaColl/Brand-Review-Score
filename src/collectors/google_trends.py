"""Google Trends collector via pytrends — completely free."""

from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from config.settings import DEFAULT_CONFIG
from src.collectors.base import BaseCollector
from src.models.brand import Brand
from src.models.review import Review, ReviewCollection

logger = logging.getLogger(__name__)


class GoogleTrendsCollector(BaseCollector):
    """Collects Google Trends search interest data for a brand.

    Uses pytrends (unofficial Google Trends scraper).
    Free, but rate-limited — use sparingly.

    The "reviews" it returns are synthetic: each data point becomes a Review
    with the normalized interest value stored in the rating field (0–100 scale
    mapped to 1–5) so it integrates with the scoring pipeline.
    """

    name = "google_trends"

    def __init__(self, config: object | None = None) -> None:
        super().__init__()
        cfg = config or DEFAULT_CONFIG
        self.timeframe = cfg.google_trends_timeframe
        self.geo = cfg.google_trends_geo

    def _collect(self, brand: Brand) -> ReviewCollection:
        try:
            from pytrends.request import TrendReq
        except ImportError:
            logger.warning("pytrends not installed — skipping Google Trends collection.")
            return ReviewCollection(brand_name=brand.name)

        reviews: list[Review] = []
        # Use the primary search term
        keyword = brand.search_terms[0] if brand.search_terms else brand.name

        try:
            pytrends = TrendReq(hl="en-US", tz=360, retries=2, backoff_factor=0.5)
            pytrends.build_payload([keyword], timeframe=self.timeframe, geo=self.geo)
            interest_df: pd.DataFrame = pytrends.interest_over_time()

            if interest_df.empty:
                logger.info("No Google Trends data for '%s'", keyword)
                return ReviewCollection(brand_name=brand.name)

            for date_idx, row in interest_df.iterrows():
                interest_value = float(row[keyword])
                # Map 0-100 interest to 1-5 rating scale for pipeline compatibility
                normalized_rating = 1.0 + (interest_value / 100.0) * 4.0

                ts = date_idx.to_pydatetime() if isinstance(date_idx, pd.Timestamp) else datetime.utcnow()

                reviews.append(
                    Review(
                        text=f"Google Trends interest: {interest_value}/100 for '{keyword}'",
                        source=self.name,
                        timestamp=ts,
                        rating=normalized_rating,
                        engagement=int(interest_value),
                    )
                )

        except Exception as exc:
            logger.warning("Google Trends fetch failed for '%s': %s", keyword, exc)

        return ReviewCollection(brand_name=brand.name, reviews=reviews)

    def get_raw_interest(self, brand: Brand) -> pd.DataFrame:
        """Return raw interest-over-time DataFrame for advanced analysis."""
        try:
            from pytrends.request import TrendReq
        except ImportError:
            return pd.DataFrame()

        keyword = brand.search_terms[0] if brand.search_terms else brand.name
        try:
            pytrends = TrendReq(hl="en-US", tz=360, retries=2, backoff_factor=0.5)
            pytrends.build_payload([keyword], timeframe=self.timeframe, geo=self.geo)
            return pytrends.interest_over_time()
        except Exception as exc:
            logger.warning("Google Trends raw fetch failed for '%s': %s", keyword, exc)
            return pd.DataFrame()
