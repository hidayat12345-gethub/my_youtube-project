"""Optional live-action client.

The dashboard is read-only against holy_month.db by default (works
with just the GitHub Actions deployment, nothing else to run). If a
FastAPI backend (`python holy_month_automation.py web`) is *also*
reachable — locally or on a host you point this at — the dashboard
uses it for actions that actually need to happen live: approve,
reject, and "produce this video now" all call YouTube / Gemini /
ffmpeg, which a read-only dashboard can't do by itself.

Every function here fails soft: on any error/timeout it returns
{"ok": False, "error": "..."} instead of raising, so the UI can just
show "backend not reachable" instead of crashing.
"""

import os
from typing import Dict

import requests

DEFAULT_BASE_URL = os.getenv("HOLY_MONTH_API_URL", "http://localhost:8000")
TIMEOUT = 5

# FIX (audit): matches the backend's new opt-in API_ACCESS_TOKEN
# protection (holy_month/api/security.py). Unset by default — sends no
# header, matching the backend's local/dev no-auth default. Set
# HOLY_MONTH_API_KEY in the environment this dashboard runs in (NOT the
# same variable name as the backend's .env, so the two can't be
# confused with each other) to match a backend that has
# API_ACCESS_TOKEN configured.
_API_KEY = os.getenv("HOLY_MONTH_API_KEY", "")


def _auth_headers() -> Dict:
    return {"X-API-Key": _API_KEY} if _API_KEY else {}


def is_backend_available(base_url: str = DEFAULT_BASE_URL) -> bool:
    try:
        resp = requests.get(f"{base_url}/health", timeout=TIMEOUT)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def _request(method: str, path: str, base_url: str = DEFAULT_BASE_URL, timeout: int = 30, **kwargs) -> Dict:
    try:
        headers = {**_auth_headers(), **kwargs.pop("headers", {})}
        resp = requests.request(method, f"{base_url}{path}", timeout=timeout, headers=headers, **kwargs)
        if resp.status_code == 401:
            return {"ok": False, "error": "Unauthorized — backend requires an API key. Set "
                                           "HOLY_MONTH_API_KEY in this dashboard's environment "
                                           "to match the backend's API_ACCESS_TOKEN."}
        resp.raise_for_status()
        return {"ok": True, "data": resp.json()}
    except requests.RequestException as e:
        return {"ok": False, "error": str(e)}


def _post(path: str, base_url: str = DEFAULT_BASE_URL, **kwargs) -> Dict:
    return _request("POST", path, base_url, **kwargs)


def approve_video(video_id: int, base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _post(f"/api/v1/videos/{video_id}/approve", base_url)


def reject_video(video_id: int, base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _post(f"/api/v1/videos/{video_id}/reject", base_url)


def produce_next(plan_id: int, base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _post(f"/api/v1/produce-next/{plan_id}", base_url)


def pause_plan(plan_id: int, base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _post(f"/api/v1/plans/{plan_id}/pause", base_url)


def resume_plan(plan_id: int, base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _post(f"/api/v1/plans/{plan_id}/resume", base_url)


def create_plan(payload: Dict, base_url: str = DEFAULT_BASE_URL) -> Dict:
    # Generates ~30 ideas via Gemini before responding — needs more
    # than the default 30s timeout other actions use.
    return _request("POST", "/api/v1/monthly-plan", base_url, timeout=120, json=payload)


def update_plan(plan_id: int, payload: Dict, base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _request("PUT", f"/api/v1/plans/{plan_id}", base_url, json=payload)


def delete_plan(plan_id: int, base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _request("DELETE", f"/api/v1/plans/{plan_id}", base_url)


def duplicate_plan(plan_id: int, reuse_ideas: bool = False, base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _request("POST", f"/api/v1/plans/{plan_id}/duplicate", base_url, timeout=120,
                     json={"reuse_ideas": reuse_ideas})


def regenerate_ideas(plan_id: int, base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _request("POST", f"/api/v1/plans/{plan_id}/regenerate-ideas", base_url, timeout=120)


# ============================================================
# Video Editor (Module 4)
# ============================================================

def update_video_metadata(video_id: int, payload: Dict, base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _request("PUT", f"/api/v1/videos/{video_id}/metadata", base_url, json=payload)


def set_ai_disclosure(video_id: int, value: str, base_url: str = DEFAULT_BASE_URL) -> Dict:
    """value: 'yes' | 'no' | 'not_selected' — YouTube Altered/Synthetic
    content disclosure. See holy_month/api/routes_videos.py's
    set_ai_disclosure endpoint for the full flow."""
    return _request("PUT", f"/api/v1/videos/{video_id}/ai-disclosure", base_url, json={"value": value})


def update_video_script(video_id: int, payload: Dict, base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _request("PUT", f"/api/v1/videos/{video_id}/script", base_url, json=payload)


def regenerate_video_thumbnail(video_id: int, base_url: str = DEFAULT_BASE_URL) -> Dict:
    # Generates a fresh image via Pollinations.ai + optionally pushes to YouTube
    return _request("POST", f"/api/v1/videos/{video_id}/regenerate-thumbnail", base_url, timeout=60)


def regenerate_video_full(video_id: int, voice: str = "en", language: str = None,
                           base_url: str = DEFAULT_BASE_URL) -> Dict:
    # Full re-render: voice + images + assembly + re-upload. Can genuinely
    # take a few minutes for a multi-scene video.
    payload = {"voice": voice}
    if language:
        payload["language"] = language
    return _request("POST", f"/api/v1/videos/{video_id}/regenerate", base_url, timeout=600, json=payload)


# ============================================================
# Analytics + YouTube (Module 5)
# ============================================================

def sync_youtube_stats(base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _request("POST", "/api/v1/youtube/sync-stats", base_url, timeout=60)


def get_channel_summary(base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _request("GET", "/api/v1/youtube/channel-summary", base_url, timeout=15)


def get_channel_analytics(days: int = 28, base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _request("GET", f"/api/v1/youtube/analytics?days={days}", base_url, timeout=20)


def get_recent_comments(max_results: int = 10, base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _request("GET", f"/api/v1/youtube/comments?max_results={max_results}", base_url, timeout=15)


# ============================================================
# AI Settings (Module 6)
# ============================================================

def get_ai_settings(base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _request("GET", "/api/v1/settings", base_url, timeout=10)


def update_ai_settings(payload: Dict, base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _request("PUT", "/api/v1/settings", base_url, json=payload)


def reset_ai_settings(base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _request("POST", "/api/v1/settings/reset", base_url)


def get_prompt_templates(base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _request("GET", "/api/v1/settings/prompts", base_url, timeout=10)


def update_prompt_template(key: str, text: str, base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _request("PUT", f"/api/v1/settings/prompts/{key}", base_url, json={"text": text})


def reset_prompt_template(key: str, base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _request("POST", f"/api/v1/settings/prompts/{key}/reset", base_url)


# ============================================================
# System Settings (Module 6)
# ============================================================

def get_output_folder(base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _request("GET", "/api/v1/system/output-folder", base_url, timeout=15)


def cleanup_temp_folders(base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _request("POST", "/api/v1/system/cleanup-temp-folders", base_url, timeout=30)


def snapshot_db(base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _request("POST", "/api/v1/system/snapshot-db", base_url, timeout=30)


def list_snapshots(base_url: str = DEFAULT_BASE_URL) -> Dict:
    return _request("GET", "/api/v1/system/snapshots", base_url, timeout=10)


def download_backup_bytes(base_url: str = DEFAULT_BASE_URL):
    """Returns raw bytes (not the usual {ok, data} shape) since this is
    a file download, or None on failure."""
    try:
        resp = requests.get(f"{base_url}/api/v1/system/backup-db", timeout=30, headers=_auth_headers())
        resp.raise_for_status()
        return resp.content
    except requests.RequestException:
        return None


def restore_db(file_bytes: bytes, filename: str, base_url: str = DEFAULT_BASE_URL) -> Dict:
    try:
        resp = requests.post(f"{base_url}/api/v1/system/restore-db", timeout=30, headers=_auth_headers(),
                              files={"file": (filename, file_bytes, "application/octet-stream")})
        resp.raise_for_status()
        return {"ok": True, "data": resp.json()}
    except requests.RequestException as e:
        return {"ok": False, "error": str(e)}


# ============================================================
# Logs (Module 6)
# ============================================================

def get_logs(lines: int = 300, base_url: str = DEFAULT_BASE_URL) -> str:
    """Returns raw log text, or '' on failure — the Logs page prefers
    reading the local log file directly (works without a live backend),
    this is only used as a fallback when the backend runs elsewhere."""
    try:
        resp = requests.get(f"{base_url}/api/v1/system/logs", params={"lines": lines}, timeout=10,
                             headers=_auth_headers())
        resp.raise_for_status()
        return resp.text
    except requests.RequestException:
        return ""
