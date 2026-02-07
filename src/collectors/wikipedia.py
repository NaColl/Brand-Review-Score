"""Wikipedia Pageviews collector — completely free, no API key."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import requests

from config.settings import DEFAULT_CONFIG
from src.collectors.base import BaseCollector
from src.models.brand import Brand
from src.models.review import Review, ReviewCollection

logger = logging.getLogger(__name__)


class WikipediaCollector(BaseCollector):
    """Collects daily Wikipedia pageview counts as a brand awareness proxy.

    Uses the Wikimedia REST API — completely free, no key required.
    Pageviews correlate with public interest and awareness spikes.
    """

    name = "wikipedia"

    _API_BASE = (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
        "/{project}/all-access/user/{article}/daily/{start}/{end}"
    )

    def __init__(self, config: object | None = None) -> None:
        super().__init__()
        cfg = config or DEFAULT_CONFIG
        self.project = cfg.wikipedia_project
        self.lookback_days = cfg.wikipedia_lookback_days
        self.timeout = cfg.request_timeout

    def _collect(self, brand: Brand) -> ReviewCollection:
        article = brand.wikipedia_article
        if not article:
            logger.info("No Wikipedia article configured for '%s'", brand.name)
            return ReviewCollection(brand_name=brand.name)

        end = datetime.utcnow()
        start = end - timedelta(days=self.lookback_days)

        url = self._API_BASE.format(
            project=f"{self.project}.org",
            article=article,
            start=start.strftime("%Y%m%d"),
            end=end.strftime("%Y%m%d"),
        )
        headers = {
            "User-Agent": "BrandSentimentScore/1.0 (brand-review-score@example.com)"
        }

        resp = requests.get(url, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        reviews: list[Review] = []
        for item in data.get("items", []):
            views = item.get("views", 0)
            date_str = item.get("timestamp", "")
            try:
                ts = datetime.strptime(date_str[:8], "%Y%m%d")
            except (ValueError, IndexError):
                ts = datetime.utcnow()

            reviews.append(
                Review(
                    text=f"Wikipedia pageviews: {views:,} for '{article}'",
                    source=self.name,
                    timestamp=ts,
                    engagement=views,
                )
            )

        return ReviewCollection(brand_name=brand.name, reviews=reviews)

    def get_raw_pageviews(self, brand: Brand) -> list[dict]:
        """Return raw daily pageview data for advanced analysis."""
        article = brand.wikipedia_article
        if not article:
            return []

        end = datetime.utcnow()
        start = end - timedelta(days=self.lookback_days)

        url = self._API_BASE.format(
            project=f"{self.project}.org",
            article=article,
            start=start.strftime("%Y%m%d"),
            end=end.strftime("%Y%m%d"),
        )
        headers = {
            "User-Agent": "BrandSentimentScore/1.0 (brand-review-score@example.com)"
        }

        try:
            resp = requests.get(url, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json().get("items", [])
        except Exception as exc:
            logger.warning("Wikipedia pageview fetch failed for '%s': %s", article, exc)
            return []
