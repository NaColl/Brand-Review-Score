"""BSS SaaS — Modal Cloud Deployment.

Deploy:
    modal deploy modal_app.py

Serve locally (dev):
    modal serve modal_app.py

The app will be live at:
    https://<your-workspace>--bss-api-serve.modal.run
"""

import modal

# ─────────────────────────────────────────────────────────────────────────
# Modal App + Image + Volume
# ─────────────────────────────────────────────────────────────────────────

app = modal.App("bss-api")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi>=0.110",
        "uvicorn[standard]>=0.27",
        "pydantic>=2.5",
        "apscheduler>=3.10",
        "vaderSentiment>=3.3",
        "textblob>=0.18",
        "numpy>=1.24",
        "pandas>=2.0",
        "pyyaml>=6.0",
        "rich>=13.0",
        "click>=8.1",
        "requests>=2.31",
        "python-dateutil>=2.8",
        "atoma>=0.0.17",
        "praw>=7.7",
        "pytrends>=4.9",
        "beautifulsoup4>=4.12",
    )
    .add_local_dir("src", remote_path="/app/src", copy=True)
    .add_local_dir("config", remote_path="/app/config", copy=True)
    .add_local_dir("dashboard", remote_path="/app/dashboard", copy=True)
    .add_local_file("server.py", remote_path="/app/server.py", copy=True)
    .add_local_file("cli.py", remote_path="/app/cli.py", copy=True)
)

# Persistent volume for SQLite database (survives redeploys)
volume = modal.Volume.from_name("bss-data", create_if_missing=True)

DATA_DIR = "/data"


# ─────────────────────────────────────────────────────────────────────────
# Web API (FastAPI)
# ─────────────────────────────────────────────────────────────────────────

@app.function(
    image=image,
    volumes={DATA_DIR: volume},
    scaledown_window=300,
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def serve():
    """Serve the BSS FastAPI application."""
    import sys
    sys.path.insert(0, "/app")

    # Point database to persistent volume
    from src import database
    from pathlib import Path
    database.DB_PATH = Path(DATA_DIR) / "bss.db"

    from server import app as fastapi_app
    return fastapi_app


# ─────────────────────────────────────────────────────────────────────────
# Scheduled Scoring (runs daily at 6 AM UTC)
# ─────────────────────────────────────────────────────────────────────────

@app.function(
    image=image,
    volumes={DATA_DIR: volume},
    timeout=3600,
    schedule=modal.Cron("0 6 * * *"),
)
def scheduled_scoring():
    """Auto-score all brands with auto_score=True. Runs daily at 6 AM UTC."""
    import sys
    sys.path.insert(0, "/app")

    from src import database
    from pathlib import Path
    database.DB_PATH = Path(DATA_DIR) / "bss.db"
    database.init_db()

    import json
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("bss.scheduled")

    from src.database import get_db, save_score, get_previous_score, check_and_create_alerts
    from src.models.brand import Brand
    from src.prediction.signals import SignalGenerator
    from src.scoring.composite import BSSCalculator

    logger.info("Scheduled scoring run starting...")

    with get_db() as db:
        rows = db.execute(
            "SELECT b.*, k.id as key_id FROM brands b "
            "JOIN api_keys k ON b.api_key_id = k.id "
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

    volume.commit()
    logger.info("Scheduled scoring complete — scored %d/%d brands", scored, len(rows))
