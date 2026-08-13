"""NEW MODULE (Module 6) — a tiny JSON-file-backed settings store.

Deliberately NOT a new DB table: these are process-wide generation
knobs (temperature, model name, thumbnail/caption styling), not
per-video or per-plan data, so a flat file that's easy to hand-edit or
version-control alongside .env fits better than a DB row. Lives at
holy_month_settings.json in the repo root (same level as .env and
holy_month.db) — created with defaults on first access.
"""

import json
import os
from typing import Any, Dict

SETTINGS_PATH = "holy_month_settings.json"

DEFAULTS: Dict[str, Any] = {
    "gemini_model": None,       # None = fall back to Config.GEMINI_MODEL
    "gemini_temperature": 0.9,  # Gemini's own default is ~1.0; a touch lower
                                 # biases toward more consistent, less erratic
                                 # topic/script generation for a recurring
                                 # educational series.
    "thumbnail_text_color": "#FFD700",
    "thumbnail_font_size": 56,
    "caption_font_size": 20,
}


def _load() -> Dict[str, Any]:
    if not os.path.exists(SETTINGS_PATH):
        return dict(DEFAULTS)
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULTS)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULTS)


def _save(data: Dict[str, Any]) -> None:
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_all_settings() -> Dict[str, Any]:
    return _load()


def get_setting(key: str) -> Any:
    return _load().get(key, DEFAULTS.get(key))


def update_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    data = _load()
    data.update({k: v for k, v in updates.items() if k in DEFAULTS})
    _save(data)
    return data


def reset_settings() -> Dict[str, Any]:
    _save(dict(DEFAULTS))
    return dict(DEFAULTS)
