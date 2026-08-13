"""NEW MODULE (Module 6) — persisted logs.

The pipeline has always communicated via print(), not Python's logging
module. That's fine for watching a live terminal, but it means nothing
survives after the process exits — and for the GitHub Actions
deployment, nothing survives past that job finishing at all.

Rewriting every print() call across every agent/service/route to
logger.info() would touch dozens of files for zero behavior change —
exactly the "rewrite working code" this project has avoided everywhere
else. Instead, this installs a Tee on sys.stdout/stderr that duplicates
every write to BOTH the real console (so a live terminal or a GitHub
Actions log looks identical to before) AND a local file. Every
existing print() gets captured for free.

Does NOT solve persistence for the GitHub Actions deployment — that
runner's filesystem is thrown away after the job (and committing raw
log files back to the repo alongside holy_month.db would be noisy).
For that deployment, GitHub's own Actions tab remains the place to
read a given day's log — the Logs dashboard page says this plainly
rather than pretending to show something it can't.
"""

import os
import sys
from datetime import datetime

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "holy_month.log")
MAX_LOG_SIZE_BYTES = 5 * 1024 * 1024  # 5MB — simple home-grown rotation,
                                       # see _truncate_if_too_large()

_initialized = False


def _truncate_if_too_large():
    """No log rotation library involved — just keeps the tail if the
    file has grown past MAX_LOG_SIZE_BYTES, so a long-running `web`
    process doesn't grow this file forever."""
    if not os.path.exists(LOG_FILE):
        return
    if os.path.getsize(LOG_FILE) <= MAX_LOG_SIZE_BYTES:
        return
    with open(LOG_FILE, "rb") as f:
        f.seek(-MAX_LOG_SIZE_BYTES // 2, os.SEEK_END)
        tail = f.read()
    with open(LOG_FILE, "wb") as f:
        f.write(b"...[earlier log truncated]...\n")
        f.write(tail)


class _StreamTee:
    def __init__(self, stream, log_file_handle):
        self._stream = stream
        self._log_file_handle = log_file_handle

    def write(self, data):
        self._stream.write(data)
        try:
            self._log_file_handle.write(data)
            self._log_file_handle.flush()
        except Exception:
            pass  # never let a logging failure take down the actual pipeline

    def flush(self):
        self._stream.flush()
        try:
            self._log_file_handle.flush()
        except Exception:
            pass

    def isatty(self):
        return getattr(self._stream, "isatty", lambda: False)()


def setup_logging():
    """Idempotent — safe to call from multiple entrypoints (main.py's
    module top AND cli.py's main()) without double-wrapping stdout."""
    global _initialized
    if _initialized:
        return
    os.makedirs(LOG_DIR, exist_ok=True)
    _truncate_if_too_large()

    log_handle = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
    log_handle.write(f"\n{'=' * 70}\n🕌 Holy Month AI session started {datetime.now().isoformat()}\n{'=' * 70}\n")

    sys.stdout = _StreamTee(sys.stdout, log_handle)
    sys.stderr = _StreamTee(sys.stderr, log_handle)
    _initialized = True


def read_log_tail(max_lines: int = 300) -> str:
    if not os.path.exists(LOG_FILE):
        return ""
    with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    return "".join(lines[-max_lines:])
