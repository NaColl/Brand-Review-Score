"""Base collector interface for all data sources."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

from src.models.brand import Brand
from src.models.review import ReviewCollection

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """Abstract base class for data collectors.

    Every collector follows the same contract:
    1. Accept a Brand object.
    2. Return a ReviewCollection (possibly empty on failure).
    3. Handle its own rate-limiting and retries internally.
    """

    name: str = "base"

    def __init__(self, max_retries: int = 3, backoff: float = 2.0) -> None:
        self.max_retries = max_retries
        self.backoff = backoff

    def collect(self, brand: Brand) -> ReviewCollection:
        """Collect data with automatic retries on transient failures."""
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                result = self._collect(brand)
                logger.info(
                    "%s collected %d items for '%s'",
                    self.name, result.count, brand.name,
                )
                return result
            except Exception as exc:
                last_error = exc
                wait = self.backoff ** attempt
                logger.warning(
                    "%s attempt %d/%d failed for '%s': %s — retrying in %.1fs",
                    self.name, attempt, self.max_retries, brand.name, exc, wait,
                )
                time.sleep(wait)

        logger.error(
            "%s failed after %d attempts for '%s': %s",
            self.name, self.max_retries, brand.name, last_error,
        )
        return ReviewCollection(brand_name=brand.name)

    @abstractmethod
    def _collect(self, brand: Brand) -> ReviewCollection:
        """Subclasses implement the actual data fetching here."""
        ...
