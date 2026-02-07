"""Reddit collector via PRAW — free, 60 requests/minute."""

from __future__ import annotations

import logging
from datetime import datetime

from config.settings import DEFAULT_CONFIG
from src.collectors.base import BaseCollector
from src.models.brand import Brand
from src.models.review import Review, ReviewCollection

logger = logging.getLogger(__name__)


class RedditCollector(BaseCollector):
    """Collects Reddit posts and top comments about a brand.

    Requires REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables.
    Free tier: 60 requests/minute, no monthly cost.

    Falls back to an empty collection if credentials are missing.
    """

    name = "reddit"

    def __init__(self, config: object | None = None) -> None:
        super().__init__()
        cfg = config or DEFAULT_CONFIG
        self.client_id = cfg.reddit_client_id
        self.client_secret = cfg.reddit_client_secret
        self.user_agent = cfg.reddit_user_agent
        self.default_subreddits = cfg.reddit_subreddits
        self.post_limit = cfg.reddit_post_limit
        self._reddit = None

    def _get_reddit(self):
        """Lazy-initialize PRAW client."""
        if self._reddit is not None:
            return self._reddit

        if not self.client_id or not self.client_secret:
            logger.warning(
                "Reddit credentials not set — set REDDIT_CLIENT_ID and "
                "REDDIT_CLIENT_SECRET environment variables. Skipping Reddit collection."
            )
            return None

        try:
            import praw
            self._reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent,
            )
            return self._reddit
        except ImportError:
            logger.warning("praw not installed — skipping Reddit collection.")
            return None

    def _collect(self, brand: Brand) -> ReviewCollection:
        reddit = self._get_reddit()
        if reddit is None:
            return ReviewCollection(brand_name=brand.name)

        reviews: list[Review] = []
        subreddits = list(set(self.default_subreddits + brand.subreddits))

        for sub_name in subreddits:
            try:
                subreddit = reddit.subreddit(sub_name)
                for term in brand.search_terms:
                    for submission in subreddit.search(
                        term, limit=self.post_limit, sort="relevance", time_filter="month"
                    ):
                        # Add the post title + selftext
                        text = submission.title
                        if submission.selftext:
                            text += " " + submission.selftext[:500]

                        reviews.append(
                            Review(
                                text=text,
                                source=self.name,
                                timestamp=datetime.utcfromtimestamp(submission.created_utc),
                                author=str(submission.author) if submission.author else None,
                                url=f"https://reddit.com{submission.permalink}",
                                engagement=submission.score,
                            )
                        )

                        # Add top-level comments (top 5 by score)
                        submission.comment_sort = "best"
                        submission.comments.replace_more(limit=0)
                        for comment in submission.comments[:5]:
                            if hasattr(comment, "body") and len(comment.body) > 10:
                                reviews.append(
                                    Review(
                                        text=comment.body[:1000],
                                        source=self.name,
                                        timestamp=datetime.utcfromtimestamp(comment.created_utc),
                                        author=str(comment.author) if comment.author else None,
                                        engagement=comment.score,
                                    )
                                )
            except Exception as exc:
                logger.warning("Error fetching r/%s for '%s': %s", sub_name, brand.name, exc)

        return ReviewCollection(brand_name=brand.name, reviews=reviews)
