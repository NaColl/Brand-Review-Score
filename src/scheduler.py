"""Background scheduler for automated brand scoring.

Runs BSS scoring on a schedule (daily/weekly) for all registered brands
with auto_score=True.
"""

from __future__ import annotations

import json
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from src.database import (
    check_and_create_alerts,
    get_previous_score,
    save_score,
)

logger = logging.getLogger("bss.scheduler")


def _score_all_brands():
    """Score all brands that have auto_score enabled."""
    from src.database import get_db
    from src.models.brand import Brand
    from src.prediction.signals import SignalGenerator
    from src.scoring.composite import BSSCalculator

    logger.info("Scheduler: starting automated scoring run...")

    with get_db() as db:
        rows = db.execute(
            "SELECT b.*, k.id as key_id FROM brands b JOIN api_keys k ON b.api_key_id = k.id "
            "WHERE b.auto_score = 1 AND k.is_active = 1"
        ).fetchall()

    scored = 0
    for row in rows:
        brand_dict = dict(row)
        try:
            brand_model = Brand(
                name=brand_dict["name"],
                ticker=brand_dict.get("ticker"),
                search_terms=json.loads(brand_dict.get("search_terms", "[]")),
                wikipedia_article=brand_dict.get("wikipedia_article", brand_dict["name"].replace(" ", "_")),
                subreddits=json.loads(brand_dict.get("subreddits", "[]")),
                competitors=json.loads(brand_dict.get("competitors", "[]")),
                category=brand_dict.get("category", "general"),
            )

            force_luxury = True if brand_dict.get("is_luxury") else None
            calculator = BSSCalculator(sentiment_engine="vader", force_luxury=force_luxury)

            bss = calculator.calculate(
                brand_model,
                sale_percentage=brand_dict.get("sale_percentage"),
                avg_discount_pct=brand_dict.get("avg_discount_pct"),
                resale_value_ratio=brand_dict.get("resale_value_ratio"),
            )

            signal = SignalGenerator().generate(bss)
            result = bss.to_dict()
            result["predictive_signal"] = signal.to_dict()

            score_id = save_score(brand_dict["id"], result)
            prev = get_previous_score(brand_dict["id"])
            check_and_create_alerts(brand_dict["id"], score_id, result, prev)

            scored += 1
            logger.info("  Scored '%s': %.1f (%s)", brand_dict["name"], bss.bss, bss.grade())

        except Exception as e:
            logger.error("  Failed to score '%s': %s", brand_dict["name"], e)

    logger.info("Scheduler: finished — scored %d/%d brands", scored, len(rows))


def start_scheduler() -> BackgroundScheduler:
    """Start the background scoring scheduler."""
    scheduler = BackgroundScheduler()

    # Run daily at 6 AM UTC
    scheduler.add_job(_score_all_brands, "cron", hour=6, minute=0, id="daily_scoring")

    # Also run every 4 hours for pro/enterprise brands
    scheduler.add_job(_score_all_brands, "interval", hours=4, id="frequent_scoring")

    scheduler.start()
    logger.info("Scheduler started — daily at 06:00 UTC + every 4 hours")
    return scheduler
