import os
import shutil as _shutil
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import FileResponse, PlainTextResponse

from holy_month.config import Config
from holy_month.db import SessionLocal, Video
from holy_month.logging_setup import read_log_tail, LOG_FILE
from holy_month.services.system_admin import (
    get_output_folder_summary, cleanup_temp_folders, get_db_path,
    create_db_snapshot, list_db_snapshots, restore_db_from_bytes,
)
from .security import verify_api_key

router = APIRouter(tags=["system"])


@router.get("/")
async def root():
    return {"name": "Holy Month AI - YouTube Automation", "version": "1.1.0", "status": "running",
            "endpoints": ["/health", "/api/v1/monthly-plan", "/api/v1/plans", "/api/v1/videos",
                          "/api/v1/videos/{id}/approve", "/api/v1/videos/{id}/reject",
                          "/api/v1/produce-next/{plan_id}", "/api/v1/status"]}


@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat(),
            "config": {"gemini": bool(Config.GEMINI_API_KEY),
                       "youtube_authorized": bool(Config.YOUTUBE_REFRESH_TOKEN),
                       "telegram": bool(Config.TELEGRAM_BOT_TOKEN),
                       "require_human_review": Config.REQUIRE_HUMAN_REVIEW,
                       "auto_approve_after_hours": Config.AUTO_APPROVE_AFTER_HOURS,
                       "publish_hour": Config.PUBLISH_HOUR,
                       # NEW (Module 6):
                       "ffmpeg": _shutil.which("ffmpeg") is not None}}


@router.get("/api/v1/status")
async def get_status():
    db = SessionLocal()
    try:
        total_videos = db.query(Video).count()
        published = db.query(Video).filter(Video.status.in_(['published', 'auto_published'])).count()
        auto_published = db.query(Video).filter(Video.status == 'auto_published').count()
        pending_review = db.query(Video).filter(Video.status == 'pending_review').count()
        latest = db.query(Video).order_by(Video.created_at.desc()).first()
        return {
            "system_status": "running", "total_videos_produced": total_videos,
            "published_count": published, "auto_published_count": auto_published,
            "pending_review_count": pending_review,
            "latest_video": ({"title": latest.title, "status": latest.status,
                              "youtube_url": latest.youtube_url,
                              "created_at": latest.created_at.isoformat()} if latest else None),
        }
    finally:
        db.close()


# ============================================================
# NEW (Module 6) — System Settings
# ============================================================

@router.get("/api/v1/system/output-folder")
async def output_folder_summary():
    return get_output_folder_summary()


@router.post("/api/v1/system/cleanup-temp-folders", dependencies=[Depends(verify_api_key)])
async def cleanup_output_folder():
    """Removes temp work_*/regen_* directories that no video currently
    references. See services/system_admin.py for the safety check."""
    return cleanup_temp_folders()


@router.get("/api/v1/system/backup-db", dependencies=[Depends(verify_api_key)])
async def download_backup():
    """Streams the CURRENT live database file directly — the simplest
    form of 'backup' is just downloading it."""
    db_path = get_db_path()
    return FileResponse(db_path, filename=f"holy_month_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                         media_type="application/octet-stream")


@router.post("/api/v1/system/snapshot-db", dependencies=[Depends(verify_api_key)])
async def snapshot_db():
    """Copies the current DB into backups/ on the server, timestamped —
    useful before a risky operation (e.g. before a Monthly Planner
    delete) without leaving the dashboard."""
    result = create_db_snapshot()
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    return result


@router.get("/api/v1/system/snapshots", dependencies=[Depends(verify_api_key)])
async def snapshots():
    return {"snapshots": list_db_snapshots()}


@router.post("/api/v1/system/restore-db", dependencies=[Depends(verify_api_key)])
async def restore_db(file: UploadFile = File(...)):
    """Validates the uploaded file is a real holy_month.db before doing
    anything, auto-snapshots the current DB first so this is itself
    reversible, then swaps the file in. Restarting the server
    afterwards is recommended — see system_admin.restore_db_from_bytes
    docstring for why."""
    contents = await file.read()
    result = restore_db_from_bytes(contents)
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    return result


@router.get("/api/v1/system/logs", response_class=PlainTextResponse)
async def get_logs(lines: int = 300):
    return read_log_tail(max_lines=lines)


@router.get("/api/v1/system/logs/download")
async def download_logs():
    if not os.path.exists(LOG_FILE):
        raise HTTPException(404, "No log file yet.")
    return FileResponse(LOG_FILE, filename="holy_month.log", media_type="text/plain")
