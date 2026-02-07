"""Dimension 5 — Competitive Position Score (CPS).

The "floor layer" of the Sentiment Iceberg.
Measures how a brand stacks up against its direct competitors.

Components:
    1. Relative Rating (40%) — Brand rating vs category average
    2. Share of Voice (30%) — Percentage of category mentions
    3. Sentiment Gap (30%) — Sentiment advantage vs closest competitor
"""

from __future__ import annotations

from config.settings import CPS_WEIGHTS
from src.models.review import ReviewCollection
from src.models.score import CompetitivePositionScore


def calculate_competitive_position(
    brand_collection: ReviewCollection,
    competitor_collections: dict[str, ReviewCollection],
) -> CompetitivePositionScore:
    """Calculate Competitive Position Score.

    Args:
        brand_collection: The brand's own review/mention data.
        competitor_collections: Dict mapping competitor name → their data.
    """
    components: dict[str, float] = {}

    all_collections = {"__brand__": brand_collection}
    all_collections.update(competitor_collections)

    # ---- 1. Relative Rating ----
    components["relative_rating"] = _relative_rating(brand_collection, competitor_collections)

    # ---- 2. Share of Voice ----
    components["share_of_voice"] = _share_of_voice(brand_collection, competitor_collections)

    # ---- 3. Sentiment Gap ----
    components["sentiment_gap"] = _sentiment_gap(brand_collection, competitor_collections)

    # Weighted sum → 0–100
    value = sum(
        components[k] * CPS_WEIGHTS[k] * 100
        for k in CPS_WEIGHTS
    )

    explanation = _build_explanation(components, brand_collection, competitor_collections)

    return CompetitivePositionScore(
        value=value,
        components=components,
        explanation=explanation,
    )


def _relative_rating(
    brand: ReviewCollection,
    competitors: dict[str, ReviewCollection],
) -> float:
    """Brand's average sentiment relative to category average.

    Score > 0.5 means the brand outperforms peers.
    Score < 0.5 means the brand underperforms.
    """
    brand_sentiment = brand.average_sentiment
    if brand_sentiment is None:
        return 0.5

    peer_sentiments = []
    for comp_collection in competitors.values():
        s = comp_collection.average_sentiment
        if s is not None:
            peer_sentiments.append(s)

    if not peer_sentiments:
        # No competitor data — score based on absolute sentiment
        return max(0.0, min(1.0, (brand_sentiment + 1) / 2))

    category_avg = sum(peer_sentiments) / len(peer_sentiments)

    # How much better/worse than the category average
    gap = brand_sentiment - category_avg

    # Map gap to [0, 1]: gap of +0.5 → 0.75, gap of -0.5 → 0.25
    return max(0.0, min(1.0, 0.5 + gap))


def _share_of_voice(
    brand: ReviewCollection,
    competitors: dict[str, ReviewCollection],
) -> float:
    """Percentage of total category mentions belonging to this brand.

    Higher share of voice = stronger market presence.
    """
    brand_count = brand.count
    total_count = brand_count + sum(c.count for c in competitors.values())

    if total_count == 0:
        return 0.5

    share = brand_count / total_count

    # If there are N competitors + 1 brand, fair share = 1/(N+1)
    n_players = 1 + len(competitors)
    fair_share = 1.0 / n_players

    if fair_share == 0:
        return 0.5

    # Ratio of actual share to fair share
    # ratio > 1 = overrepresented (good), ratio < 1 = underrepresented
    ratio = share / fair_share

    # Map to [0, 1]: ratio of 2 → 0.8, ratio of 0.5 → 0.35
    return max(0.0, min(1.0, 0.3 + ratio * 0.35))


def _sentiment_gap(
    brand: ReviewCollection,
    competitors: dict[str, ReviewCollection],
) -> float:
    """Sentiment advantage over the closest (strongest) competitor.

    This specifically compares against the best competitor, not the average.
    Leading the strongest rival is more meaningful than beating the average.
    """
    brand_sentiment = brand.average_sentiment
    if brand_sentiment is None:
        return 0.5

    best_competitor_sentiment = None
    for comp_collection in competitors.values():
        s = comp_collection.average_sentiment
        if s is not None:
            if best_competitor_sentiment is None or s > best_competitor_sentiment:
                best_competitor_sentiment = s

    if best_competitor_sentiment is None:
        return max(0.0, min(1.0, (brand_sentiment + 1) / 2))

    gap = brand_sentiment - best_competitor_sentiment

    # Map gap to [0, 1]
    return max(0.0, min(1.0, 0.5 + gap))


def _build_explanation(
    components: dict[str, float],
    brand: ReviewCollection,
    competitors: dict[str, ReviewCollection],
) -> str:
    parts: list[str] = []
    n_comp = len(competitors)

    rr = components["relative_rating"]
    if rr > 0.6:
        parts.append(f"Rating above {n_comp} peer(s)")
    elif rr < 0.4:
        parts.append(f"Rating below {n_comp} peer(s)")
    else:
        parts.append(f"Rating in line with {n_comp} peer(s)")

    sov = components["share_of_voice"]
    if sov > 0.65:
        parts.append("Dominant share of voice")
    elif sov > 0.5:
        parts.append("Above-average share of voice")
    elif sov > 0.35:
        parts.append("Below-average share of voice")
    else:
        parts.append("Weak share of voice")

    sg = components["sentiment_gap"]
    if sg > 0.6:
        parts.append("Sentiment leads top competitor")
    elif sg < 0.4:
        parts.append("Sentiment trails top competitor")
    else:
        parts.append("Sentiment close to top competitor")

    return "; ".join(parts)
