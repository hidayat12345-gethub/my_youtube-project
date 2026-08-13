import json
from typing import Dict

from holy_month.utils import gemini_json


class ScriptWriterAgent:
    def write_script(self, title: str, theme: str, research: Dict, duration: str = "5min") -> Dict:
        # NEW (Module 6): AI Settings prompt template (lazy import — see
        # planner.py for why). Default text is byte-for-byte the original;
        # the four research fields are pre-serialized to JSON strings
        # before substitution since Template only fills $placeholders,
        # it doesn't know how to json.dumps() a list itself.
        from holy_month.services.prompt_templates import render
        prompt = render(
            "script_writer", title=title, theme=theme, duration=duration,
            quran_json=json.dumps(research.get('quran_references', [])),
            hadith_json=json.dumps(research.get('hadith_references', [])),
            facts_json=json.dumps(research.get('historical_facts', [])),
            keywords_json=json.dumps(research.get('keywords', [])),
        )
        result = gemini_json(prompt)
        if result and isinstance(result, dict) and result.get("body"):
            return result

        print(f"⚠️  Script Writer: Gemini unavailable for '{title}' — using template fallback.")
        return self._write_with_template(title, theme, research, duration)

    def _write_with_template(self, title: str, theme: str, research: Dict, duration: str) -> Dict:
        verses = research.get('quran_references', [])
        hadiths = research.get('hadith_references', [])

        verse_text = (f'Allah says in the Quran, Surah {verses[0]["surah"]}: "{verses[0]["text"]}"'
                      if verses else "")
        hadith_text = (f'The Prophet (peace be upon him) said: "{hadiths[0]["text"]}"'
                       if hadiths else "")

        return {
            "title": f"{title} - Islamic Guidance"[:60],
            "hook": f"Assalamu Alaikum! Today we explore {title}.",
            "introduction": f"In this video, we'll discuss {title} and its importance in Islamic teachings.",
            "body": [
                verse_text or f"Let's reflect on the meaning of {title}.",
                hadith_text or "The Prophet's teachings guide us here.",
                "Learn practical ways to apply this in your daily life.",
                "Discover the wisdom behind this teaching.",
            ],
            "ending": f"In conclusion, {title} teaches us valuable lessons about our faith.",
            "call_to_action": "If you found this beneficial, please like, share, and subscribe.",
            "description": f"Learn about {title} in this insightful video. Subscribe for more Islamic content.",
            "tags": research.get('keywords', [])[:10],
            "hashtags": [f"#{theme}", "#IslamicTeachings", "#MuslimGuide"],
            "pinned_comment": "JazakAllah Khair for watching! Share your thoughts in the comments.",
        }
