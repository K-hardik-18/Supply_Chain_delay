"""
history.py  —  SQLite-backed prediction history.

Stores every /predict-delay and /optimize-route result
for analytics and trend tracking.

Database: data/history.db (auto-created)
"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path

DB_PATH = "data/history.db"


def _get_conn():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS predictions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT NOT NULL,
            source          TEXT NOT NULL,
            destination     TEXT NOT NULL,
            departure_time  TEXT NOT NULL,
            vehicle_type    TEXT NOT NULL,
            cargo_type      TEXT NOT NULL,
            priority_level  INTEGER NOT NULL,
            delay_probability REAL NOT NULL,
            delayed         INTEGER NOT NULL,
            risk_level      TEXT NOT NULL,
            model_name      TEXT,
            top_factors     TEXT,
            context         TEXT
        );

        CREATE TABLE IF NOT EXISTS route_optimizations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT NOT NULL,
            source          TEXT NOT NULL,
            destination     TEXT NOT NULL,
            departure_time  TEXT NOT NULL,
            vehicle_type    TEXT NOT NULL,
            cargo_type      TEXT NOT NULL,
            priority_level  INTEGER NOT NULL,
            best_route      TEXT NOT NULL,
            total_distance  REAL NOT NULL,
            estimated_time  REAL NOT NULL,
            mean_delay_risk REAL NOT NULL,
            route_score     REAL NOT NULL,
            n_candidates    INTEGER NOT NULL,
            segments        TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_pred_ts ON predictions(timestamp);
        CREATE INDEX IF NOT EXISTS idx_pred_src ON predictions(source);
        CREATE INDEX IF NOT EXISTS idx_route_ts ON route_optimizations(timestamp);
    """)
    conn.commit()
    conn.close()


def save_prediction(request: dict, response: dict, model_name: str = "xgboost"):
    """Save a /predict-delay result to history."""
    conn = _get_conn()
    conn.execute("""
        INSERT INTO predictions (
            timestamp, source, destination, departure_time,
            vehicle_type, cargo_type, priority_level,
            delay_probability, delayed, risk_level,
            model_name, top_factors, context
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        request["source"],
        request["destination"],
        request["departure_time"],
        request["vehicle_type"],
        request["cargo_type"],
        request["priority_level"],
        response["delay_probability"],
        int(response["delayed"]),
        response["risk_level"],
        model_name,
        json.dumps(response.get("top_factors", [])),
        json.dumps(response.get("context", {})),
    ))
    conn.commit()
    conn.close()


def save_route(request: dict, response: dict):
    """Save a /optimize-route result to history."""
    best = response["best_route"]
    conn = _get_conn()
    conn.execute("""
        INSERT INTO route_optimizations (
            timestamp, source, destination, departure_time,
            vehicle_type, cargo_type, priority_level,
            best_route, total_distance, estimated_time,
            mean_delay_risk, route_score, n_candidates, segments
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        request["source"],
        request["destination"],
        request["departure_time"],
        request["vehicle_type"],
        request["cargo_type"],
        request["priority_level"],
        json.dumps(best["route"]),
        best["total_distance_km"],
        best.get("estimated_time_hr", 0),
        best["mean_delay_risk"],
        best["route_score"],
        response["summary"]["n_candidates"],
        json.dumps(best.get("segments", [])),
    ))
    conn.commit()
    conn.close()


def get_predictions(limit: int = 100, offset: int = 0) -> list[dict]:
    """Fetch recent predictions."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM predictions ORDER BY timestamp DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_routes(limit: int = 100, offset: int = 0) -> list[dict]:
    """Fetch recent route optimizations."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM route_optimizations ORDER BY timestamp DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_analytics() -> dict:
    """Aggregate analytics for the dashboard."""
    conn = _get_conn()

    # Total counts
    total_preds = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    total_routes = conn.execute("SELECT COUNT(*) FROM route_optimizations").fetchone()[0]

    if total_preds == 0:
        conn.close()
        return {
            "total_predictions": 0,
            "total_routes": 0,
            "avg_delay_probability": 0,
            "delay_rate": 0,
            "risk_distribution": {},
            "top_risky_routes": [],
            "hourly_delay_trend": [],
            "recent_predictions": [],
        }

    # Averages
    avg_delay = conn.execute("SELECT AVG(delay_probability) FROM predictions").fetchone()[0] or 0
    delay_rate = conn.execute("SELECT AVG(delayed) FROM predictions").fetchone()[0] or 0

    # Risk distribution
    risk_rows = conn.execute(
        "SELECT risk_level, COUNT(*) as cnt FROM predictions GROUP BY risk_level"
    ).fetchall()
    risk_dist = {r["risk_level"]: r["cnt"] for r in risk_rows}

    # Top risky routes
    risky = conn.execute("""
        SELECT source, destination,
               COUNT(*) as count,
               AVG(delay_probability) as avg_risk,
               SUM(delayed) as delayed_count
        FROM predictions
        GROUP BY source, destination
        ORDER BY avg_risk DESC
        LIMIT 5
    """).fetchall()
    top_risky = [dict(r) for r in risky]

    # Hourly delay trend (from departure_time)
    hourly = conn.execute("""
        SELECT
            CAST(SUBSTR(departure_time, 12, 2) AS INTEGER) as hour,
            AVG(delay_probability) as avg_risk,
            COUNT(*) as count
        FROM predictions
        GROUP BY hour
        ORDER BY hour
    """).fetchall()
    hourly_trend = [dict(r) for r in hourly]

    # Recent predictions (last 20)
    recent = conn.execute(
        "SELECT * FROM predictions ORDER BY timestamp DESC LIMIT 20"
    ).fetchall()
    recent_list = [dict(r) for r in recent]

    conn.close()

    return {
        "total_predictions": total_preds,
        "total_routes": total_routes,
        "avg_delay_probability": round(avg_delay, 4),
        "delay_rate": round(delay_rate, 4),
        "risk_distribution": risk_dist,
        "top_risky_routes": top_risky,
        "hourly_delay_trend": hourly_trend,
        "recent_predictions": recent_list,
    }


def clear_history():
    """Wipe all prediction and route history from the database."""
    conn = _get_conn()
    conn.execute("DELETE FROM predictions")
    conn.execute("DELETE FROM route_optimizations")
    conn.commit()
    conn.close()


# Initialize on import
init_db()
