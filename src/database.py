"""SQLite persistence layer for BSS SaaS.

Stores brands, historical scores, API keys, and alerts.
Uses raw sqlite3 — no ORM, no extra dependencies.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

DB_PATH = Path(__file__).parent.parent / "data" / "bss.db"

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _local.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = _get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db() -> None:
    """Create all tables if they don't exist."""
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_hash TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                tier TEXT NOT NULL DEFAULT 'starter',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                is_active INTEGER NOT NULL DEFAULT 1,
                rate_limit INTEGER NOT NULL DEFAULT 100,
                brands_limit INTEGER NOT NULL DEFAULT 10
            );

            CREATE TABLE IF NOT EXISTS brands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_key_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                ticker TEXT,
                wikipedia_article TEXT,
                search_terms TEXT NOT NULL DEFAULT '[]',
                subreddits TEXT NOT NULL DEFAULT '[]',
                competitors TEXT NOT NULL DEFAULT '[]',
                category TEXT NOT NULL DEFAULT 'general',
                is_luxury INTEGER NOT NULL DEFAULT 0,
                sale_percentage REAL,
                avg_discount_pct REAL,
                resale_value_ratio REAL,
                auto_score INTEGER NOT NULL DEFAULT 1,
                score_frequency TEXT NOT NULL DEFAULT 'daily',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (api_key_id) REFERENCES api_keys(id),
                UNIQUE(api_key_id, name)
            );

            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand_id INTEGER NOT NULL,
                scored_at TEXT NOT NULL DEFAULT (datetime('now')),
                bss REAL NOT NULL,
                grade TEXT NOT NULL,
                is_luxury INTEGER NOT NULL DEFAULT 0,
                confidence REAL NOT NULL DEFAULT 0,
                data_sources TEXT NOT NULL DEFAULT '[]',
                total_data_points INTEGER NOT NULL DEFAULT 0,
                dimensions TEXT NOT NULL DEFAULT '{}',
                hype_health TEXT,
                luxury_index TEXT,
                predictive_signal TEXT,
                raw_json TEXT NOT NULL,
                FOREIGN KEY (brand_id) REFERENCES brands(id)
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand_id INTEGER NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'info',
                message TEXT NOT NULL,
                score_id INTEGER,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                is_read INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (brand_id) REFERENCES brands(id),
                FOREIGN KEY (score_id) REFERENCES scores(id)
            );

            CREATE INDEX IF NOT EXISTS idx_scores_brand ON scores(brand_id, scored_at DESC);
            CREATE INDEX IF NOT EXISTS idx_alerts_brand ON alerts(brand_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_brands_api_key ON brands(api_key_id);
        """)


# ─────────────────────────────────────────────────────────────────────────
# API Keys
# ─────────────────────────────────────────────────────────────────────────

TIER_LIMITS = {
    "starter": {"rate_limit": 100, "brands_limit": 10},
    "pro": {"rate_limit": 1000, "brands_limit": 50},
    "enterprise": {"rate_limit": 10000, "brands_limit": 500},
}


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def create_api_key(name: str, tier: str = "starter") -> tuple[str, int]:
    """Create a new API key. Returns (raw_key, key_id)."""
    raw_key = f"bss_{secrets.token_urlsafe(32)}"
    limits = TIER_LIMITS.get(tier, TIER_LIMITS["starter"])
    with get_db() as db:
        cursor = db.execute(
            "INSERT INTO api_keys (key_hash, name, tier, rate_limit, brands_limit) VALUES (?, ?, ?, ?, ?)",
            (_hash_key(raw_key), name, tier, limits["rate_limit"], limits["brands_limit"]),
        )
        return raw_key, cursor.lastrowid


def validate_api_key(raw_key: str) -> dict | None:
    """Validate an API key. Returns key info or None."""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM api_keys WHERE key_hash = ? AND is_active = 1",
            (_hash_key(raw_key),),
        ).fetchone()
        return dict(row) if row else None


# ─────────────────────────────────────────────────────────────────────────
# Brands
# ─────────────────────────────────────────────────────────────────────────

def create_brand(api_key_id: int, **kwargs) -> int:
    """Register a brand to track. Returns brand_id."""
    with get_db() as db:
        # Check brand limit
        count = db.execute(
            "SELECT COUNT(*) FROM brands WHERE api_key_id = ?", (api_key_id,)
        ).fetchone()[0]
        limit = db.execute(
            "SELECT brands_limit FROM api_keys WHERE id = ?", (api_key_id,)
        ).fetchone()[0]
        if count >= limit:
            raise ValueError(f"Brand limit reached ({limit}). Upgrade your plan.")

        cursor = db.execute(
            """INSERT INTO brands
               (api_key_id, name, ticker, wikipedia_article, search_terms,
                subreddits, competitors, category, is_luxury,
                sale_percentage, avg_discount_pct, resale_value_ratio,
                auto_score, score_frequency)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                api_key_id,
                kwargs["name"],
                kwargs.get("ticker"),
                kwargs.get("wikipedia_article", kwargs["name"].replace(" ", "_")),
                json.dumps(kwargs.get("search_terms", [kwargs["name"]])),
                json.dumps(kwargs.get("subreddits", [])),
                json.dumps(kwargs.get("competitors", [])),
                kwargs.get("category", "general"),
                1 if kwargs.get("is_luxury", False) else 0,
                kwargs.get("sale_percentage"),
                kwargs.get("avg_discount_pct"),
                kwargs.get("resale_value_ratio"),
                1 if kwargs.get("auto_score", True) else 0,
                kwargs.get("score_frequency", "daily"),
            ),
        )
        return cursor.lastrowid


def get_brands(api_key_id: int) -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM brands WHERE api_key_id = ? ORDER BY name", (api_key_id,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["search_terms"] = json.loads(d["search_terms"])
            d["subreddits"] = json.loads(d["subreddits"])
            d["competitors"] = json.loads(d["competitors"])
            result.append(d)
        return result


def get_brand(brand_id: int, api_key_id: int) -> dict | None:
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM brands WHERE id = ? AND api_key_id = ?",
            (brand_id, api_key_id),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["search_terms"] = json.loads(d["search_terms"])
        d["subreddits"] = json.loads(d["subreddits"])
        d["competitors"] = json.loads(d["competitors"])
        return d


def delete_brand(brand_id: int, api_key_id: int) -> bool:
    with get_db() as db:
        cursor = db.execute(
            "DELETE FROM brands WHERE id = ? AND api_key_id = ?",
            (brand_id, api_key_id),
        )
        return cursor.rowcount > 0


# ─────────────────────────────────────────────────────────────────────────
# Scores
# ─────────────────────────────────────────────────────────────────────────

def save_score(brand_id: int, score_data: dict) -> int:
    """Save a BSS score result. Returns score_id."""
    with get_db() as db:
        cursor = db.execute(
            """INSERT INTO scores
               (brand_id, bss, grade, is_luxury, confidence,
                data_sources, total_data_points, dimensions,
                hype_health, luxury_index, predictive_signal, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                brand_id,
                score_data["bss"],
                score_data["grade"],
                1 if score_data.get("is_luxury", False) else 0,
                score_data.get("confidence", 0),
                json.dumps(score_data.get("data_sources_used", [])),
                score_data.get("total_data_points", 0),
                json.dumps(score_data.get("dimensions", {})),
                json.dumps(score_data.get("hype_health_index")) if score_data.get("hype_health_index") else None,
                json.dumps(score_data.get("luxury_brand_index")) if score_data.get("luxury_brand_index") else None,
                json.dumps(score_data.get("predictive_signal")) if score_data.get("predictive_signal") else None,
                json.dumps(score_data),
            ),
        )
        return cursor.lastrowid


def get_latest_score(brand_id: int) -> dict | None:
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM scores WHERE brand_id = ? ORDER BY scored_at DESC LIMIT 1",
            (brand_id,),
        ).fetchone()
        return _parse_score_row(row) if row else None


def get_score_history(brand_id: int, limit: int = 90) -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM scores WHERE brand_id = ? ORDER BY scored_at DESC LIMIT ?",
            (brand_id, limit),
        ).fetchall()
        return [_parse_score_row(r) for r in rows]


def get_previous_score(brand_id: int) -> dict | None:
    """Get the second-most-recent score for delta calculation."""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM scores WHERE brand_id = ? ORDER BY scored_at DESC LIMIT 1 OFFSET 1",
            (brand_id,),
        ).fetchone()
        return _parse_score_row(row) if row else None


def _parse_score_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["data_sources"] = json.loads(d["data_sources"])
    d["dimensions"] = json.loads(d["dimensions"])
    if d["hype_health"]:
        d["hype_health"] = json.loads(d["hype_health"])
    if d["luxury_index"]:
        d["luxury_index"] = json.loads(d["luxury_index"])
    if d["predictive_signal"]:
        d["predictive_signal"] = json.loads(d["predictive_signal"])
    if d["raw_json"]:
        d["raw_json"] = json.loads(d["raw_json"])
    return d


# ─────────────────────────────────────────────────────────────────────────
# Alerts
# ─────────────────────────────────────────────────────────────────────────

def create_alert(brand_id: int, alert_type: str, message: str,
                 severity: str = "info", score_id: int | None = None) -> int:
    with get_db() as db:
        cursor = db.execute(
            "INSERT INTO alerts (brand_id, alert_type, severity, message, score_id) VALUES (?, ?, ?, ?, ?)",
            (brand_id, alert_type, severity, message, score_id),
        )
        return cursor.lastrowid


def get_alerts(api_key_id: int, unread_only: bool = False, limit: int = 50) -> list[dict]:
    with get_db() as db:
        query = """
            SELECT a.*, b.name as brand_name FROM alerts a
            JOIN brands b ON a.brand_id = b.id
            WHERE b.api_key_id = ?
        """
        if unread_only:
            query += " AND a.is_read = 0"
        query += " ORDER BY a.created_at DESC LIMIT ?"
        rows = db.execute(query, (api_key_id, limit)).fetchall()
        return [dict(r) for r in rows]


def mark_alerts_read(api_key_id: int) -> int:
    with get_db() as db:
        cursor = db.execute(
            """UPDATE alerts SET is_read = 1
               WHERE brand_id IN (SELECT id FROM brands WHERE api_key_id = ?) AND is_read = 0""",
            (api_key_id,),
        )
        return cursor.rowcount


def check_and_create_alerts(brand_id: int, score_id: int, current: dict, previous: dict | None) -> list[dict]:
    """Generate alerts based on score changes."""
    alerts = []
    bss = current["bss"]
    grade = current["grade"]

    if previous:
        delta = bss - previous["bss"]

        if delta <= -8:
            a = create_alert(brand_id, "bss_crash", f"BSS dropped {delta:.1f} pts to {bss:.1f} ({grade})",
                             severity="critical", score_id=score_id)
            alerts.append({"type": "bss_crash", "severity": "critical", "delta": delta})
        elif delta <= -3:
            a = create_alert(brand_id, "bss_decline", f"BSS declined {delta:.1f} pts to {bss:.1f} ({grade})",
                             severity="warning", score_id=score_id)
            alerts.append({"type": "bss_decline", "severity": "warning", "delta": delta})
        elif delta >= 8:
            a = create_alert(brand_id, "bss_surge", f"BSS surged +{delta:.1f} pts to {bss:.1f} ({grade})",
                             severity="info", score_id=score_id)
            alerts.append({"type": "bss_surge", "severity": "info", "delta": delta})

        if previous["grade"] != grade:
            direction = "upgraded" if bss > previous["bss"] else "downgraded"
            a = create_alert(brand_id, "grade_change",
                             f"Grade {direction}: {previous['grade']} → {grade}",
                             severity="warning" if direction == "downgraded" else "info",
                             score_id=score_id)
            alerts.append({"type": "grade_change", "direction": direction})

    # HHI alerts
    hhi = current.get("hype_health_index")
    if hhi:
        quadrant = hhi.get("quadrant")
        if quadrant == "overhyped":
            create_alert(brand_id, "hhi_overhyped", "Brand is in OVERHYPED quadrant — bubble risk",
                         severity="warning", score_id=score_id)
            alerts.append({"type": "hhi_overhyped"})
        elif quadrant == "declining":
            create_alert(brand_id, "hhi_declining", "Brand is in DECLINING quadrant — low hype and low health",
                         severity="critical", score_id=score_id)
            alerts.append({"type": "hhi_declining"})

    # Pricing alerts
    dims = current.get("dimensions", {})
    pricing = dims.get("pricing_intelligence", {})
    if pricing.get("explanation", "").startswith("Sale %:"):
        explanation = pricing.get("explanation", "")
        if "ALERT" in explanation:
            create_alert(brand_id, "high_sale_pct", f"Pricing alert: {explanation[:100]}",
                         severity="warning", score_id=score_id)
            alerts.append({"type": "high_sale_pct"})

    return alerts
