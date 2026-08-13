"""NEW MODULE (Module 6) — editable prompt templates.

Uses string.Template ($placeholder syntax) rather than str.format —
these prompts contain literal JSON examples full of {curly braces}
(e.g. '{"day": 1, "title": "...", ...}'), which would need every brace
escaped to {{ }} under str.format. $placeholders sidestep that
entirely since Template only touches $identifiers.

Every DEFAULT_* string below is byte-for-byte the original hardcoded
prompt from planner.py / research.py / script_writer.py, just with the
f-string {var} spots swapped for $var. Nobody who never opens AI
Settings will see any behavior change — these are only read as
fallbacks when no override is stored.
"""

import json
import os
from string import Template
from typing import Dict

TEMPLATES_PATH = "holy_month_prompt_templates.json"

DEFAULT_PLANNER_PROMPT = """You are a content strategist for Islamic educational YouTube content.

Generate exactly $count video ideas for a channel covering the theme
"$theme" during "$holy_month", for the audience: "$target_audience",
in language: "$language".

Requirements:
- Cover a logical progression across the month (early/mid/late themes),
  not $count random unrelated topics.
- No two ideas should repeat the same angle.
- Each idea needs a specific, non-generic title (not "Ramadan Day 5" — an
  actual topic) and a 1-sentence summary a scriptwriter could expand from.
- Tone: respectful, authentic, educational — no sensationalism, no
  presenting disputed matters as settled fact.

Respond with ONLY a JSON array of exactly $count objects, no other text:
[{"day": 1, "title": "...", "summary": "..."}, ...]
"""

DEFAULT_RESEARCH_PROMPT = """You are a research assistant for Islamic educational YouTube content.
Video topic: "$topic" (theme: $theme)

Produce a research package with:
- quran_references: list of {"surah": str, "verse": int, "text": str}.
  Only include verses you're confident about; if unsure of exact numbering,
  note that uncertainty in a "note" field rather than guessing.
- hadith_references: list of {"source": str, "number": str, "text": str,
  "grade": str}. Only include hadith with a commonly recognized source and
  grading. If disputed, say so in "grade" rather than presenting it as certain.
- historical_facts: list of 2-4 strings, specific to THIS topic.
- keywords: list of 8-12 SEO strings for THIS specific topic.
- audience_interest: 1 sentence on why this matters to viewers now.

Respond with ONLY a JSON object with those five keys, no other text.
"""

DEFAULT_SCRIPT_WRITER_PROMPT = """You are a professional Islamic content creator writing a YouTube script.

Title: $title
Theme: $theme
Duration: $duration

Research:
Quran: $quran_json
Hadith: $hadith_json
Historical facts: $facts_json
Keywords: $keywords_json

Write a complete script as a JSON object with these exact keys:
- "title": catchy title, max 60 characters
- "hook": 1-2 sentences, first thing said
- "introduction": 2-3 sentences
- "body": a JSON ARRAY of 4-6 strings, each one narration paragraph
  (this is used to generate one visual scene per paragraph, so each
  entry should describe a distinct beat/idea, not just be an arbitrary
  text split)
- "ending": 1-2 sentences
- "call_to_action": 1 sentence (like/subscribe, not pushy)
- "description": YouTube description, 2-3 paragraphs, keyword-rich
- "tags": array of 10-15 strings
- "hashtags": array of 5-8 strings, each starting with #
- "pinned_comment": 1 sentence

Respond with ONLY the JSON object, no other text, no markdown fences.
"""

DEFAULTS: Dict[str, str] = {
    "planner": DEFAULT_PLANNER_PROMPT,
    "research": DEFAULT_RESEARCH_PROMPT,
    "script_writer": DEFAULT_SCRIPT_WRITER_PROMPT,
}


def _load() -> Dict[str, str]:
    if not os.path.exists(TEMPLATES_PATH):
        return dict(DEFAULTS)
    try:
        with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULTS)
        merged.update({k: v for k, v in data.items() if k in DEFAULTS})
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULTS)


def _save(data: Dict[str, str]) -> None:
    with open(TEMPLATES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_all_templates() -> Dict[str, str]:
    return _load()


def get_template(key: str) -> str:
    return _load().get(key, DEFAULTS.get(key, ""))


def set_template(key: str, text: str) -> None:
    if key not in DEFAULTS:
        raise KeyError(f"Unknown template '{key}' — must be one of {list(DEFAULTS)}")
    data = _load()
    data[key] = text
    _save(data)


def reset_template(key: str) -> str:
    if key not in DEFAULTS:
        raise KeyError(f"Unknown template '{key}' — must be one of {list(DEFAULTS)}")
    data = _load()
    data[key] = DEFAULTS[key]
    _save(data)
    return DEFAULTS[key]


def render(key: str, **kwargs) -> str:
    """Renders the stored (or default) template with $placeholders
    filled in. Falls back to the hardcoded default and logs a warning
    if a user-edited template is missing a placeholder the agent needs
    — better than crashing production on a typo in AI Settings."""
    template_text = get_template(key)
    try:
        return Template(template_text).substitute(**kwargs)
    except KeyError as e:
        print(f"⚠️  Prompt template '{key}' is missing placeholder {e} — "
              f"falling back to the default template for this call.")
        return Template(DEFAULTS[key]).substitute(**kwargs)
