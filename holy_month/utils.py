"""Small shared helpers used by several agents. Verbatim from the
original single file."""

import json
import os
import re
import subprocess
from typing import Any, Optional

from PIL import ImageFont

from holy_month.config import Config, get_genai_client


def strip_json_fences(text: str) -> str:
    """Gemini commonly wraps JSON in ```json ... ``` fences (or adds a
    leading sentence). A bare json.loads(response.text) throws on most
    real responses, so this strips fences and grabs the outermost
    {...} or [...] before parsing."""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'```\s*$', '', text)
    match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
    return match.group(1) if match else text


def gemini_json(prompt: str, model_name: str = None, temperature: float = None) -> Optional[Any]:
    """Call Gemini and return parsed JSON, or None if it fails for any
    reason (missing key, quota hit, malformed response) so callers can
    fall back to their static/template logic instead of crashing.

    model_name/temperature default to the AI Settings store (Module 6)
    when not passed explicitly — lazy-imported here (not at module
    top) to avoid a circular import: holy_month.services imports
    agents, which imports this module, so importing
    holy_month.services back at the top of THIS module would be a
    cycle. By call time everything's already loaded, so a local import
    is safe."""
    client = get_genai_client()
    if not client:
        return None

    from holy_month.services.settings_store import get_setting
    resolved_model = model_name or get_setting("gemini_model") or Config.GEMINI_MODEL
    resolved_temperature = temperature if temperature is not None else get_setting("gemini_temperature")

    try:
        try:
            from google.genai import types
            config = types.GenerateContentConfig(temperature=resolved_temperature)
            response = client.models.generate_content(
                model=resolved_model, contents=prompt, config=config,
            )
        except TypeError:
            # Defensive fallback: if the installed google-genai version's
            # generate_content() signature doesn't accept `config` the way
            # expected here, fall back to the original call with no
            # temperature control rather than hard-failing every AI call.
            response = client.models.generate_content(model=resolved_model, contents=prompt)
        cleaned = strip_json_fences(response.text)
        return json.loads(cleaned)
    except Exception as e:
        print(f"⚠️  Gemini call failed, using fallback: {e}")
        return None


def get_audio_duration_seconds(path: str) -> float:
    """Uses ffprobe (comes bundled with ffmpeg, which is required anyway)."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 5.0  # safe fallback so assembly doesn't crash on a bad probe


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttf",
        "C:/Windows/Fonts/Arial.ttf",
    ):
        if os.path.exists(candidate):
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()
