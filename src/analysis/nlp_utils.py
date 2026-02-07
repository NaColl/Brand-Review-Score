"""Text preprocessing and aspect extraction utilities."""

from __future__ import annotations

import re
import string


# Common aspect categories for brand reviews
ASPECT_KEYWORDS: dict[str, list[str]] = {
    "quality": [
        "quality", "build", "durable", "reliable", "craftsmanship",
        "well-made", "well made", "premium", "cheap", "flimsy",
    ],
    "service": [
        "service", "support", "customer service", "help desk", "response",
        "representative", "agent", "wait time", "helpful", "rude",
    ],
    "value": [
        "price", "value", "expensive", "affordable", "worth", "overpriced",
        "cost", "deal", "bargain", "rip off", "ripoff",
    ],
    "innovation": [
        "innovative", "innovation", "new feature", "cutting edge", "technology",
        "advanced", "modern", "outdated", "behind", "leading",
    ],
    "experience": [
        "experience", "easy", "difficult", "intuitive", "confusing",
        "seamless", "frustrating", "smooth", "user-friendly", "clunky",
    ],
}


def preprocess_text(text: str) -> str:
    """Clean and normalize text for sentiment analysis.

    Steps:
    1. Lowercase
    2. Remove URLs
    3. Remove excessive whitespace
    4. Preserve sentiment-relevant punctuation (! ?)
    5. Remove non-ASCII noise
    """
    if not text:
        return ""

    text = text.lower()
    # Remove URLs
    text = re.sub(r"https?://\S+|www\.\S+", "", text)
    # Remove HTML entities
    text = re.sub(r"&\w+;", " ", text)
    # Keep letters, digits, basic punctuation, spaces
    allowed = set(string.ascii_lowercase + string.digits + " !?.,'-")
    text = "".join(c if c in allowed else " " for c in text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def extract_aspects(text: str) -> dict[str, bool]:
    """Identify which aspect categories are mentioned in the text.

    Returns a dict mapping aspect name → whether it was mentioned.
    """
    lower = text.lower()
    result: dict[str, bool] = {}

    for aspect, keywords in ASPECT_KEYWORDS.items():
        result[aspect] = any(kw in lower for kw in keywords)

    return result


def count_promoter_signals(text: str, promoter_phrases: list[str]) -> int:
    """Count how many NPS-promoter phrases appear in the text."""
    lower = text.lower()
    return sum(1 for phrase in promoter_phrases if phrase in lower)


def count_detractor_signals(text: str, detractor_phrases: list[str]) -> int:
    """Count how many NPS-detractor phrases appear in the text."""
    lower = text.lower()
    return sum(1 for phrase in detractor_phrases if phrase in lower)
