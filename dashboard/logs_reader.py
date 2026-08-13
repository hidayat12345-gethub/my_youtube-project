"""Reads logs/holy_month.log directly off disk — mirrors db_reader.py's
philosophy (prefer reading local state over requiring a live backend).
Works whenever this dashboard runs on the same machine/checkout as
`python holy_month_automation.py web`. Override the path with
HOLY_MONTH_LOG_PATH if the backend runs elsewhere and you've mounted
or synced its logs directory locally.

NOT available for the GitHub-Actions-only deployment: each Action run
is a fresh, ephemeral checkout, and daily-video.yml doesn't commit
logs/ back to the repo (deliberately — logs are noisy to version).
For that deployment, GitHub's own Actions tab is the place to check a
given day's output; this page says so rather than showing nothing and
letting it look broken.
"""

import os

DEFAULT_LOG_PATH = os.path.join("logs", "holy_month.log")


def get_log_path() -> str:
    return os.getenv("HOLY_MONTH_LOG_PATH", DEFAULT_LOG_PATH)


def log_exists() -> bool:
    return os.path.exists(get_log_path())


def read_log_tail(max_lines: int = 500) -> str:
    path = get_log_path()
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    return "".join(lines[-max_lines:])


def read_log_full() -> str:
    path = get_log_path()
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()
