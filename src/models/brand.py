"""Brand data model — the entity being scored."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Brand:
    """Represents a brand to be analyzed.

    Attributes:
        name:              Human-readable brand name.
        search_terms:      Terms used for news / social search.
        ticker:            Stock ticker symbol (None for private companies).
        wikipedia_article: Wikipedia article title for pageview lookups.
        subreddits:        Brand-specific subreddit names.
        competitors:       Names of direct competitors.
        category:          Industry / product category for peer comparison.
    """

    name: str
    search_terms: list[str] = field(default_factory=list)
    ticker: str | None = None
    wikipedia_article: str | None = None
    subreddits: list[str] = field(default_factory=list)
    competitors: list[str] = field(default_factory=list)
    category: str = "general"

    def __post_init__(self) -> None:
        if not self.search_terms:
            self.search_terms = [self.name]

    @classmethod
    def from_dict(cls, data: dict) -> Brand:
        return cls(
            name=data["name"],
            search_terms=data.get("search_terms", []),
            ticker=data.get("ticker"),
            wikipedia_article=data.get("wikipedia_article"),
            subreddits=data.get("subreddits", []),
            competitors=data.get("competitors", []),
            category=data.get("category", "general"),
        )
