"""BSS SaaS — FastAPI REST API Server.

Run:  uvicorn server:app --host 0.0.0.0 --port 8000 --reload
Docs: http://localhost:8000/docs
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.auth import require_api_key
from src.database import (
    check_and_create_alerts,
    create_api_key,
    create_brand,
    delete_brand,
    get_alerts,
    get_brand,
    get_brands,
    get_latest_score,
    get_previous_score,
    get_score_history,
    init_db,
    mark_alerts_read,
    save_score,
)
from src.models.brand import Brand
from src.prediction.signals import SignalGenerator
from src.scoring.composite import BSSCalculator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("bss.api")


# ─────────────────────────────────────────────────────────────────────────
# Startup / Shutdown
# ─────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("BSS SaaS API started — database initialized")
    # Start scheduler
    from src.scheduler import start_scheduler
    scheduler = start_scheduler()
    yield
    scheduler.shutdown(wait=False)
    logger.info("BSS SaaS API stopped")


app = FastAPI(
    title="Brand Sentiment Score (BSS) API",
    description="AI-powered brand intelligence platform. Track brand sentiment, "
                "predict stock movements, and benchmark competitors — from free public data.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve dashboard
DASHBOARD_DIR = Path(__file__).parent / "dashboard"
if DASHBOARD_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(DASHBOARD_DIR)), name="static")


# ─────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────────────────────────

class CreateKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Organization name")
    tier: str = Field("starter", description="Plan tier: starter, pro, enterprise")

class CreateKeyResponse(BaseModel):
    api_key: str
    key_id: int
    tier: str
    message: str

class BrandCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    ticker: str | None = None
    wikipedia_article: str | None = None
    search_terms: list[str] = []
    subreddits: list[str] = []
    competitors: list[str] = []
    category: str = "general"
    is_luxury: bool = False
    sale_percentage: float | None = Field(None, ge=0, le=1)
    avg_discount_pct: float | None = Field(None, ge=0, le=1)
    resale_value_ratio: float | None = Field(None, ge=0)
    auto_score: bool = True
    score_frequency: str = "daily"

class ScoreRequest(BaseModel):
    sale_percentage: float | None = Field(None, ge=0, le=1)
    avg_discount_pct: float | None = Field(None, ge=0, le=1)
    resale_value_ratio: float | None = Field(None, ge=0)
    engine: str = "vader"


# ─────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    index_path = DASHBOARD_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text())
    return HTMLResponse(content="<h1>BSS SaaS</h1><p>Dashboard not found. Visit /docs for API.</p>")


# ─────────────────────────────────────────────────────────────────────────
# API Key Management (public — no auth needed to create first key)
# ─────────────────────────────────────────────────────────────────────────

@app.post("/api/v1/keys", response_model=CreateKeyResponse, tags=["Authentication"])
async def create_key(req: CreateKeyRequest):
    """Create a new API key. Save it — it won't be shown again."""
    raw_key, key_id = create_api_key(req.name, req.tier)
    return CreateKeyResponse(
        api_key=raw_key,
        key_id=key_id,
        tier=req.tier,
        message="Save this API key — it cannot be retrieved later. Use it in the X-API-Key header.",
    )


# ─────────────────────────────────────────────────────────────────────────
# Brand Management
# ─────────────────────────────────────────────────────────────────────────

@app.post("/api/v1/brands", tags=["Brands"])
async def register_brand(brand: BrandCreate, key: dict = Depends(require_api_key)):
    """Register a brand to track."""
    try:
        brand_id = create_brand(key["id"], **brand.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(status_code=409, detail=f"Brand '{brand.name}' already registered")
        raise
    return {"brand_id": brand_id, "name": brand.name, "message": "Brand registered for tracking"}


@app.get("/api/v1/brands", tags=["Brands"])
async def list_brands(key: dict = Depends(require_api_key)):
    """List all tracked brands."""
    brands = get_brands(key["id"])
    # Attach latest score summary
    for b in brands:
        latest = get_latest_score(b["id"])
        if latest:
            b["latest_bss"] = latest["bss"]
            b["latest_grade"] = latest["grade"]
            b["last_scored"] = latest["scored_at"]
        else:
            b["latest_bss"] = None
            b["latest_grade"] = None
            b["last_scored"] = None
    return {"brands": brands, "count": len(brands)}


@app.get("/api/v1/brands/{brand_id}", tags=["Brands"])
async def get_brand_detail(brand_id: int, key: dict = Depends(require_api_key)):
    """Get brand details with latest score."""
    brand = get_brand(brand_id, key["id"])
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    latest = get_latest_score(brand_id)
    brand["latest_score"] = latest
    return brand


@app.delete("/api/v1/brands/{brand_id}", tags=["Brands"])
async def remove_brand(brand_id: int, key: dict = Depends(require_api_key)):
    """Remove a brand from tracking."""
    if not delete_brand(brand_id, key["id"]):
        raise HTTPException(status_code=404, detail="Brand not found")
    return {"message": "Brand removed"}


# ─────────────────────────────────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────────────────────────────────

def _brand_dict_to_model(brand_dict: dict) -> Brand:
    return Brand(
        name=brand_dict["name"],
        ticker=brand_dict.get("ticker"),
        search_terms=brand_dict.get("search_terms", [brand_dict["name"]]),
        wikipedia_article=brand_dict.get("wikipedia_article", brand_dict["name"].replace(" ", "_")),
        subreddits=brand_dict.get("subreddits", []),
        competitors=brand_dict.get("competitors", []),
        category=brand_dict.get("category", "general"),
    )


def _score_brand(brand_dict: dict, engine: str = "vader",
                 sale_pct: float | None = None,
                 discount_pct: float | None = None,
                 resale_ratio: float | None = None,
                 use_demo: bool = False) -> dict:
    """Run the scoring engine on a brand and return full results."""
    brand_model = _brand_dict_to_model(brand_dict)

    force_luxury = True if brand_dict.get("is_luxury") else None
    calculator = BSSCalculator(sentiment_engine=engine, force_luxury=force_luxury)

    # Use provided pricing or fall back to brand config
    sp = sale_pct if sale_pct is not None else brand_dict.get("sale_percentage")
    dp = discount_pct if discount_pct is not None else brand_dict.get("avg_discount_pct")
    rr = resale_ratio if resale_ratio is not None else brand_dict.get("resale_value_ratio")

    kwargs = dict(
        sale_percentage=sp,
        avg_discount_pct=dp,
        resale_value_ratio=rr,
    )

    if use_demo:
        from src.demo import generate_demo_data, generate_demo_competitors, DEMO_BRANDS
        if brand_dict["name"] in DEMO_BRANDS:
            kwargs["demo_data"] = generate_demo_data(brand_dict["name"])
            kwargs["demo_competitors"] = generate_demo_competitors(brand_dict["name"])

    bss = calculator.calculate(brand_model, **kwargs)

    # Generate signal
    signal_gen = SignalGenerator()

    # Stock price change
    price_change = None
    if use_demo:
        demo_prices = {"Nike": 5.2, "Tesla": -3.8, "Gap": -12.4}
        price_change = demo_prices.get(brand_dict["name"])
    elif brand_model.ticker:
        from src.collectors.financial import FinancialCollector
        try:
            price_change = FinancialCollector().get_price_change(brand_model, days=30)
        except Exception:
            pass

    signal = signal_gen.generate(bss, price_change_pct=price_change)

    result = bss.to_dict()
    result["predictive_signal"] = signal.to_dict()

    return result


@app.post("/api/v1/brands/{brand_id}/score", tags=["Scoring"])
async def score_brand(brand_id: int, req: ScoreRequest | None = None, key: dict = Depends(require_api_key)):
    """Score a brand now. Runs the full 8-dimension BSS engine with live data."""
    brand = get_brand(brand_id, key["id"])
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    req = req or ScoreRequest()
    result = _score_brand(
        brand, engine=req.engine,
        sale_pct=req.sale_percentage,
        discount_pct=req.avg_discount_pct,
        resale_ratio=req.resale_value_ratio,
    )

    # Save to database
    score_id = save_score(brand_id, result)

    # Check for alerts
    prev = get_previous_score(brand_id)
    alerts = check_and_create_alerts(brand_id, score_id, result, prev)

    result["score_id"] = score_id
    result["alerts"] = alerts
    return result


@app.post("/api/v1/brands/{brand_id}/demo-score", tags=["Scoring"])
async def demo_score_brand(brand_id: int, key: dict = Depends(require_api_key)):
    """Score a brand using demo data (no network required)."""
    brand = get_brand(brand_id, key["id"])
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    result = _score_brand(brand, use_demo=True)
    score_id = save_score(brand_id, result)
    prev = get_previous_score(brand_id)
    alerts = check_and_create_alerts(brand_id, score_id, result, prev)
    result["score_id"] = score_id
    result["alerts"] = alerts
    return result


@app.get("/api/v1/brands/{brand_id}/scores", tags=["Scoring"])
async def brand_score_history(
    brand_id: int,
    limit: int = Query(90, ge=1, le=365),
    key: dict = Depends(require_api_key),
):
    """Get historical BSS scores for trend analysis."""
    brand = get_brand(brand_id, key["id"])
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    history = get_score_history(brand_id, limit)
    return {
        "brand": brand["name"],
        "scores": history,
        "count": len(history),
    }


@app.get("/api/v1/brands/{brand_id}/latest", tags=["Scoring"])
async def brand_latest_score(brand_id: int, key: dict = Depends(require_api_key)):
    """Get the most recent score for a brand."""
    brand = get_brand(brand_id, key["id"])
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    latest = get_latest_score(brand_id)
    if not latest:
        raise HTTPException(status_code=404, detail="No scores yet. POST to /brands/{id}/score first.")
    return latest


# ─────────────────────────────────────────────────────────────────────────
# Comparison & Benchmarking
# ─────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/compare", tags=["Analysis"])
async def compare_brands(
    brand_ids: str = Query(..., description="Comma-separated brand IDs"),
    key: dict = Depends(require_api_key),
):
    """Compare latest BSS scores across multiple brands."""
    ids = [int(x.strip()) for x in brand_ids.split(",")]
    results = []
    for bid in ids:
        brand = get_brand(bid, key["id"])
        if not brand:
            continue
        latest = get_latest_score(bid)
        results.append({
            "brand_id": bid,
            "name": brand["name"],
            "is_luxury": bool(brand.get("is_luxury")),
            "latest": latest,
        })

    results.sort(key=lambda x: x["latest"]["bss"] if x["latest"] else 0, reverse=True)
    return {"comparison": results, "count": len(results)}


# ─────────────────────────────────────────────────────────────────────────
# Alerts
# ─────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/alerts", tags=["Alerts"])
async def list_alerts(
    unread: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    key: dict = Depends(require_api_key),
):
    """Get alerts for all tracked brands."""
    alerts = get_alerts(key["id"], unread_only=unread, limit=limit)
    return {"alerts": alerts, "count": len(alerts)}


@app.post("/api/v1/alerts/read", tags=["Alerts"])
async def mark_all_read(key: dict = Depends(require_api_key)):
    """Mark all alerts as read."""
    count = mark_alerts_read(key["id"])
    return {"marked_read": count}


# ─────────────────────────────────────────────────────────────────────────
# Dashboard API (aggregated data for the web UI)
# ─────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/dashboard", tags=["Dashboard"])
async def dashboard_data(key: dict = Depends(require_api_key)):
    """Aggregated data for the web dashboard."""
    brands = get_brands(key["id"])
    brand_summaries = []

    for b in brands:
        latest = get_latest_score(b["id"])
        history = get_score_history(b["id"], limit=30)
        trend = []
        for s in reversed(history):
            trend.append({"date": s["scored_at"], "bss": s["bss"]})

        brand_summaries.append({
            "id": b["id"],
            "name": b["name"],
            "is_luxury": bool(b.get("is_luxury")),
            "category": b.get("category", "general"),
            "bss": latest["bss"] if latest else None,
            "grade": latest["grade"] if latest else None,
            "confidence": latest["confidence"] if latest else None,
            "dimensions": latest["dimensions"] if latest else None,
            "hype_health": latest["hype_health"] if latest else None,
            "luxury_index": latest["luxury_index"] if latest else None,
            "signal": latest["predictive_signal"] if latest else None,
            "trend": trend,
            "last_scored": latest["scored_at"] if latest else None,
        })

    unread_alerts = get_alerts(key["id"], unread_only=True, limit=10)

    return {
        "brands": brand_summaries,
        "total_brands": len(brands),
        "alerts": unread_alerts,
        "alert_count": len(unread_alerts),
    }


# ─────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "version": "2.0.0", "engine": "BSS v2 — 8 Dimensions + HHI + LBI"}
