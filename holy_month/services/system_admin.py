"""NEW MODULE (Module 6) — System Settings backend: output folder
inspection + safe cleanup, and DB backup/restore.

Cleanup is deliberately conservative: work_*/regen_* directories hold
temporary per-video assets (scene audio/images, concat lists), but
ThumbnailAgent saves each video's thumbnail INSIDE its work directory
and never moves it anywhere else — meaning a thumbnail a video's DB
row still points to can live inside what looks like disposable temp
output. Blindly deleting every work_*/regen_* folder would silently
break thumbnails for videos still referencing them. So cleanup cross-
checks every candidate directory against every video's stored
video_path/thumbnail_path before removing it, and only removes
directories no video currently references.
"""

import os
import shutil
from datetime import datetime
from typing import Dict, List

from holy_month.config import Config
from holy_month.db import SessionLocal, Video, engine

BACKUP_DIR = "backups"


def get_output_folder_summary() -> Dict:
    """Top-level breakdown of Config.OUTPUT_DIR: final video/thumbnail
    files vs. temp work directories, with sizes."""
    if not os.path.exists(Config.OUTPUT_DIR):
        return {"ok": True, "total_size_bytes": 0, "final_files": [], "temp_dirs": []}

    final_files, temp_dirs = [], []
    total_size = 0

    for entry in os.scandir(Config.OUTPUT_DIR):
        if entry.is_file():
            size = entry.stat().st_size
            total_size += size
            final_files.append({"name": entry.name, "size_bytes": size,
                                 "modified": datetime.fromtimestamp(entry.stat().st_mtime).isoformat()})
        elif entry.is_dir() and (entry.name.startswith("work_") or entry.name.startswith("regen_")):
            dir_size = sum(f.stat().st_size for f in _walk_files(entry.path))
            total_size += dir_size
            temp_dirs.append({"name": entry.name, "size_bytes": dir_size,
                               "modified": datetime.fromtimestamp(entry.stat().st_mtime).isoformat()})

    final_files.sort(key=lambda x: x["modified"], reverse=True)
    temp_dirs.sort(key=lambda x: x["modified"], reverse=True)
    return {"ok": True, "total_size_bytes": total_size, "final_files": final_files, "temp_dirs": temp_dirs}


def _walk_files(path: str):
    for root, _, files in os.walk(path):
        for f in files:
            yield _StatEntry(os.path.join(root, f))


class _StatEntry:
    """Tiny shim so _walk_files can yield something with .stat() like
    os.scandir entries do, without pulling in extra dependencies."""
    def __init__(self, path):
        self._path = path

    def stat(self):
        return os.stat(self._path)


def cleanup_temp_folders() -> Dict:
    """Removes work_*/regen_* directories in OUTPUT_DIR that no video
    row currently references via video_path or thumbnail_path. Safe by
    construction — see module docstring."""
    if not os.path.exists(Config.OUTPUT_DIR):
        return {"ok": True, "removed": [], "freed_bytes": 0}

    db = SessionLocal()
    try:
        referenced_paths = set()
        for video in db.query(Video).all():
            if video.video_path:
                referenced_paths.add(os.path.abspath(video.video_path))
            if video.thumbnail_path:
                referenced_paths.add(os.path.abspath(video.thumbnail_path))
    finally:
        db.close()

    removed, freed_bytes = [], 0
    for entry in os.scandir(Config.OUTPUT_DIR):
        if not (entry.is_dir() and (entry.name.startswith("work_") or entry.name.startswith("regen_"))):
            continue
        dir_abspath = os.path.abspath(entry.path)
        is_referenced = any(p.startswith(dir_abspath + os.sep) or p == dir_abspath for p in referenced_paths)
        if is_referenced:
            continue
        dir_size = sum(f.stat().st_size for f in _walk_files(entry.path))
        try:
            shutil.rmtree(entry.path)
            removed.append(entry.name)
            freed_bytes += dir_size
        except OSError as e:
            print(f"⚠️  Couldn't remove {entry.path}: {e}")

    return {"ok": True, "removed": removed, "freed_bytes": freed_bytes}


def get_db_path() -> str:
    return Config.DATABASE_URL.replace("sqlite:///", "", 1)


def create_db_snapshot() -> Dict:
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return {"ok": False, "error": f"Database file not found at {db_path}"}
    os.makedirs(BACKUP_DIR, exist_ok=True)
    snapshot_name = f"holy_month_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    snapshot_path = os.path.join(BACKUP_DIR, snapshot_name)
    shutil.copy2(db_path, snapshot_path)
    return {"ok": True, "path": snapshot_path, "size_bytes": os.path.getsize(snapshot_path)}


def list_db_snapshots() -> List[Dict]:
    if not os.path.exists(BACKUP_DIR):
        return []
    snapshots = []
    for entry in os.scandir(BACKUP_DIR):
        if entry.is_file() and entry.name.endswith(".db"):
            snapshots.append({"name": entry.name, "size_bytes": entry.stat().st_size,
                               "modified": datetime.fromtimestamp(entry.stat().st_mtime).isoformat()})
    snapshots.sort(key=lambda x: x["modified"], reverse=True)
    return snapshots


def restore_db_from_bytes(file_bytes: bytes) -> Dict:
    """Validates the uploaded bytes are actually a readable SQLite DB
    with the expected `videos` table before touching anything, then
    auto-snapshots the CURRENT db (so a bad restore is itself
    reversible) before overwriting it.

    IMPORTANT caveat, stated here and surfaced by the API/UI: the
    running process's SQLAlchemy engine already has this file open.
    Swapping the file underneath a live engine is not a fully clean
    hot-swap for SQLite — restarting the server after a restore is
    recommended, not optional."""
    import sqlite3
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        conn = sqlite3.connect(tmp_path)
        conn.execute("SELECT COUNT(*) FROM videos")
        conn.close()
    except sqlite3.Error as e:
        os.unlink(tmp_path)
        return {"ok": False, "error": f"Uploaded file doesn't look like a valid holy_month.db: {e}"}

    snapshot = create_db_snapshot()
    if not snapshot["ok"]:
        os.unlink(tmp_path)
        return {"ok": False, "error": f"Couldn't snapshot the current DB before restoring — aborted for safety. {snapshot['error']}"}

    try:
        engine.dispose()  # best-effort close of pooled connections before swapping the file
    except Exception:
        pass

    db_path = get_db_path()
    shutil.move(tmp_path, db_path)
    return {"ok": True, "pre_restore_snapshot": snapshot["path"],
            "message": "Database restored. Restart the server for a clean reconnect."}
