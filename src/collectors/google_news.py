"""Google News RSS collector — completely free, no API key required."""

from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import quote_plus

import requests
import atoma

from config.settings import DEFAULT_CONFIG
from src.collectors.base import BaseCollector
from src.models.brand import Brand
from src.models.review import Review, ReviewCollection

logger = logging.getLogger(__name__)


class GoogleNewsCollector(BaseCollector):
    """Collects recent news headlines about a brand via Google News RSS.

    This is the single best free news source:
    - No API key required
    - No rate limits published
    - Returns titles, links, publication dates, and source names
    """

    name = "google_news"

    _RSS_BASE = (
        "https://news.google.com/rss/search"
        "?q={query}&hl={lang}&gl={country}&ceid={country}:{lang}"
    )

    def __init__(self, config: object | None = None) -> None:
        super().__init__()
        cfg = config or DEFAULT_CONFIG
        self.max_articles = cfg.google_news_max_articles
        self.language = cfg.google_news_language
        self.country = cfg.google_news_country

    def _collect(self, brand: Brand) -> ReviewCollection:
        reviews: list[Review] = []

        for term in brand.search_terms:
            url = self._RSS_BASE.format(
                query=quote_plus(term),
                lang=self.language,
                country=self.country,
            )

            try:
                resp = requests.get(url, timeout=15)
                resp.raise_for_status()
                feed = atoma.parse_rss_bytes(resp.content)
            except Exception as exc:
                logger.warning("Failed to fetch Google News RSS for '%s': %s", term, exc)
                continue

            for item in (feed.items or [])[: self.max_articles]:
                title = item.title or ""
                # Google News titles often end with " - Source Name"
                source_name = ""
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    title = parts[0]
                    source_name = parts[1] if len(parts) > 1 else ""

                published = item.pub_date or datetime.utcnow()
                if hasattr(published, "replace"):
                    published = published.replace(tzinfo=None)

                link = ""
                if item.links:
                    link = item.links[0]
                elif item.guid:
                    link = item.guid

                reviews.append(
                    Review(
                        text=title,
                        source=self.name,
                        timestamp=published,
                        url=link,
                        author=source_name,
                    )
                )

        # Deduplicate by URL
        seen_urls: set[str] = set()
        unique: list[Review] = []
        for r in reviews:
            key = r.url or r.text
            if key not in seen_urls:
                seen_urls.add(key)
                unique.append(r)

        return ReviewCollection(brand_name=brand.name, reviews=unique)
