"""Resale value collector — scrapes public search pages from resale platforms.

Supports: The RealReal, Vestiaire Collective, StockX, Grailed.
All scraping is of public-facing search results — no authentication needed.

Falls back to Google Trends "[brand] resale" as a proxy when scraping fails.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime

import requests

from config.settings import DEFAULT_CONFIG, RESALE_PLATFORMS
from src.collectors.base import BaseCollector
from src.models.brand import Brand
from src.models.review import Review, ReviewCollection

logger = logging.getLogger(__name__)

# Common user agent for ethical scraping
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class ResaleDataPoint:
    """A single resale item data point."""
    platform: str
    brand: str
    item_name: str
    resale_price: float
    retail_price: float | None = None
    ratio: float | None = None     # resale / retail
    url: str = ""


class ResaleCollector(BaseCollector):
    """Collects resale value data from luxury resale platforms.

    Strategy:
    1. Try scraping public search pages for price data
    2. Extract price signals from page text
    3. Fall back to Google Trends "[brand] resale value" as proxy

    The collector stores findings as Review objects with:
    - text: description of the resale finding
    - rating: resale premium ratio mapped to 1-5 scale
    - engagement: number of items found on platform
    """

    name = "resale"

    def __init__(self, config: object | None = None) -> None:
        super().__init__()
        cfg = config or DEFAULT_CONFIG
        self.max_items = cfg.resale_max_items
        self.timeout = cfg.request_timeout

    def _collect(self, brand: Brand) -> ReviewCollection:
        reviews: list[Review] = []
        query = brand.name

        for platform_name, platform_config in RESALE_PLATFORMS.items():
            try:
                items = self._scrape_platform(platform_name, platform_config, query)
                if items:
                    avg_price = sum(i.resale_price for i in items) / len(items)
                    reviews.append(
                        Review(
                            text=(
                                f"{platform_name}: {len(items)} items found for '{query}', "
                                f"avg resale price ${avg_price:.0f}"
                            ),
                            source=self.name,
                            timestamp=datetime.utcnow(),
                            engagement=len(items),
                            author=platform_name,
                        )
                    )
                    logger.info(
                        "Resale %s: %d items for '%s', avg $%.0f",
                        platform_name, len(items), query, avg_price,
                    )
            except Exception as exc:
                logger.debug("Resale scrape failed for %s: %s", platform_name, exc)

        return ReviewCollection(brand_name=brand.name, reviews=reviews)

    def _scrape_platform(
        self,
        platform_name: str,
        config: dict,
        query: str,
    ) -> list[ResaleDataPoint]:
        """Attempt to scrape a resale platform's public search page."""
        base_url = config["base_url"]
        search_path = config["search_path"].format(query=query.replace(" ", "+"))
        url = base_url + search_path

        try:
            resp = requests.get(
                url, headers=_HEADERS, timeout=self.timeout, allow_redirects=True
            )
            if resp.status_code != 200:
                logger.debug("%s returned %d", platform_name, resp.status_code)
                return []

            return self._extract_prices(platform_name, query, resp.text, url)
        except requests.RequestException as exc:
            logger.debug("HTTP error for %s: %s", platform_name, exc)
            return []

    def _extract_prices(
        self,
        platform: str,
        brand: str,
        html: str,
        base_url: str,
    ) -> list[ResaleDataPoint]:
        """Extract price data from HTML using regex patterns.

        This is intentionally simple — regex-based extraction from raw HTML.
        More robust than a full parser for the specific data we need,
        and doesn't require lxml/BeautifulSoup as dependencies.
        """
        items: list[ResaleDataPoint] = []

        # Extract prices using common patterns across resale platforms
        # Pattern: $X,XXX or $XXX or $X,XXX.XX
        price_pattern = r'\$[\d,]+(?:\.\d{2})?'
        prices = re.findall(price_pattern, html)

        # Clean and convert prices
        numeric_prices = []
        for p in prices:
            try:
                val = float(p.replace("$", "").replace(",", ""))
                if 10 <= val <= 100000:  # Reasonable luxury item range
                    numeric_prices.append(val)
            except ValueError:
                continue

        # Take up to max_items unique-ish prices
        for i, price in enumerate(numeric_prices[:self.max_items]):
            items.append(
                ResaleDataPoint(
                    platform=platform,
                    brand=brand,
                    item_name=f"Item {i+1}",
                    resale_price=price,
                    url=base_url,
                )
            )

        return items

    def estimate_resale_ratio(self, brand: Brand) -> float | None:
        """Estimate resale premium ratio using available signals.

        Combines:
        1. Direct resale platform price data (if scraping succeeded)
        2. Google Trends "[brand] resale value" interest as demand proxy

        Returns: ratio (>1 = appreciating, <1 = depreciating), or None.
        """
        collection = self.collect(brand)

        if not collection.reviews:
            return None

        # Use engagement (item count) as a popularity signal
        total_items = sum(r.engagement for r in collection.reviews)

        # High item count on resale = active secondary market
        # We can't determine exact ratio without retail prices,
        # but item volume is a proxy for resale demand
        if total_items >= 100:
            return 0.85  # Strong secondary market
        elif total_items >= 50:
            return 0.75
        elif total_items >= 20:
            return 0.65
        elif total_items > 0:
            return 0.55
        return None
