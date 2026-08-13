"""Read-only access to holy_month.db for the dashboard.

Deliberately uses plain sqlite3 instead of importing the holy_month
package's SQLAlchemy models — the dashboard should be runnable with
just `pip install streamlit pandas plotly requests python-dotenv`,
without needing fastapi/sqlalchemy/edge-tts/etc. installed, since in
the GitHub-Actions-only deployment nothing else needs to run on your
machine at all. This module only ever SELECTs; it never writes to the
DB (writes go through api_client.py when a live backend is reachable).
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from dotenv import dotenv_values

# Columns stored as JSON text (either a real SQLAlchemy JSON column, or
# a Text column that the pipeline itself json.dumps()'d into). Plain
# sqlite3 (unlike the SQLAlchemy ORM) doesn't auto-deserialize these —
# without this, every list field renders as a raw '["a", "b"]' string
# in the UI instead of an actual list.
_JSON_VIDEO_FIELDS = ("tags", "hashtags", "research", "scenes", "script")
_JSON_PLAN_FIELDS = ("ideas_json",)


def _parse_json_fields(row: Dict, fields) -> Dict:
    for field in fields:
        val = row.get(field)
        if isinstance(val, str) and val.strip():
            try:
                row[field] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass  # leave as raw string — better than crashing the page
    return row


def get_db_path() -> str:
    """Resolves the sqlite file path the same way Config.DATABASE_URL
    does ('sqlite:///./holy_month.db' -> './holy_month.db'), but allows
    overriding via HOLY_MONTH_DB_PATH for when the dashboard is run
    from a different working directory than the repo root."""
    override = os.getenv("HOLY_MONTH_DB_PATH")
    if override:
        return override
    url = os.getenv("DATABASE_URL", "sqlite:///./holy_month.db")
    return url.replace("sqlite:///", "", 1)


def get_env() -> Dict[str, str]:
    """Reads .env directly (not via the config package, to avoid pulling
    in the full dependency chain). Returns {} if no .env is found —
    every caller treats missing keys as 'unknown/not configured'."""
    for candidate in (".env", os.path.join(os.getcwd(), ".env")):
        if os.path.exists(candidate):
            return dotenv_values(candidate)
    return {}


def _connect() -> sqlite3.Connection:
    path = get_db_path()
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Can't find the database at '{path}'. Run this dashboard from your repo "
            f"root (same folder as holy_month.db), or set HOLY_MONTH_DB_PATH."
        )
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def db_exists() -> bool:
    return os.path.exists(get_db_path())


# ============================================================
# VIDEOS
# ============================================================

def fetch_videos(status: Optional[str] = None, search: Optional[str] = None) -> List[Dict]:
    conn = _connect()
    try:
        query = "SELECT * FROM videos"
        clauses, params = [], []
        if status and status != "All":
            clauses.append("status = ?")
            params.append(status)
        if search:
            clauses.append("title LIKE ?")
            params.append(f"%{search}%")
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [_parse_json_fields(dict(r), _JSON_VIDEO_FIELDS) for r in rows]
    finally:
        conn.close()


def fetch_video(video_id: int) -> Optional[Dict]:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
        return _parse_json_fields(dict(row), _JSON_VIDEO_FIELDS) if row else None
    finally:
        conn.close()


def fetch_pending_review() -> List[Dict]:
    """Pending-review videos, each annotated with how long until the
    auto-approval sweep will publish it (mirrors
    holy_month/services/auto_approval.py's cutoff math exactly, read-only)."""
    env = get_env()
    try:
        auto_hours = float(env.get("AUTO_APPROVE_AFTER_HOURS", "20") or "20")
    except ValueError:
        auto_hours = 20.0

    videos = fetch_videos(status="pending_review")
    now = datetime.now()
    for v in videos:
        uploaded_at = v.get("uploaded_at")
        if uploaded_at and auto_hours > 0:
            try:
                uploaded_dt = datetime.fromisoformat(uploaded_at)
                deadline = uploaded_dt + timedelta(hours=auto_hours)
                v["auto_approve_deadline"] = deadline
                v["hours_until_auto_approve"] = max(0.0, (deadline - now).total_seconds() / 3600)
                v["auto_approve_overdue"] = now >= deadline
            except ValueError:
                v["auto_approve_deadline"] = None
                v["hours_until_auto_approve"] = None
                v["auto_approve_overdue"] = False
        else:
            v["auto_approve_deadline"] = None
            v["hours_until_auto_approve"] = None
            v["auto_approve_overdue"] = False
    return videos


# ============================================================
# PLANS
# ============================================================

def fetch_plans() -> List[Dict]:
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM monthly_plans ORDER BY created_at DESC").fetchall()
        return [_parse_json_fields(dict(r), _JSON_PLAN_FIELDS) for r in rows]
    finally:
        conn.close()


def fetch_plan(plan_id: int) -> Optional[Dict]:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM monthly_plans WHERE id = ?", (plan_id,)).fetchone()
        return _parse_json_fields(dict(row), _JSON_PLAN_FIELDS) if row else None
    finally:
        conn.close()


def fetch_plan_videos(plan_id: int) -> List[Dict]:
    """NEW (Module 3) — every video produced under a plan, keyed by
    day_index, for the Monthly Planner's calendar view."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM videos WHERE plan_id = ? ORDER BY day_index ASC", (plan_id,)
        ).fetchall()
        return [_parse_json_fields(dict(r), _JSON_VIDEO_FIELDS) for r in rows]
    finally:
        conn.close()


# ============================================================
# STATUS / COUNTS
# ============================================================

def fetch_status_counts() -> Dict[str, int]:
    conn = _connect()
    try:
        rows = conn.execute("SELECT status, COUNT(*) as n FROM videos GROUP BY status").fetchall()
        counts = {r["status"]: r["n"] for r in rows}
        counts["total"] = sum(counts.values())
        counts["published_total"] = counts.get("published", 0) + counts.get("auto_published", 0)
        return counts
    finally:
        conn.close()


def fetch_latest_video() -> Optional[Dict]:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM videos ORDER BY created_at DESC LIMIT 1").fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def fetch_config_status() -> Dict[str, object]:
    """Service-configured status for the dashboard's status cards,
    read directly from .env (no need to import the agents/config
    package just to check whether a key is present)."""
    env = get_env()
    return {
        "gemini": bool(env.get("GEMINI_API_KEY")),
        "youtube_authorized": bool(env.get("YOUTUBE_REFRESH_TOKEN")),
        "telegram": bool(env.get("TELEGRAM_BOT_TOKEN") and env.get("TELEGRAM_CHAT_ID")),
        "require_human_review": str(env.get("REQUIRE_HUMAN_REVIEW", "true")).lower() == "true",
        "auto_approve_after_hours": float(env.get("AUTO_APPROVE_AFTER_HOURS", "20") or 0),
        "publish_hour": int(env.get("PUBLISH_HOUR", "8") or 8),
    }
