from typing import Dict

from holy_month.utils import gemini_json


class ResearchAgent:
    """Researches the SPECIFIC video title via Gemini, instead of
    returning the same 1-2 verses/hadith for every video under a theme.

    IMPORTANT: an LLM can misattribute a hadith's grading or a verse's
    numbering. This is a heuristic research aid, not a substitute for a
    knowledgeable human checking citations before a video goes public —
    that's exactly what the human-review gate is for. Don't disable
    that gate for religious content without a human review process."""

    _FALLBACK = {
        'ramadan': {
            "quran_references": [{"surah": "Al-Baqarah", "verse": 185,
                                   "text": "The month of Ramadan [is that] in which was revealed the Quran..."}],
            "hadith_references": [{"source": "Bukhari", "number": 1899,
                                    "text": "Whoever fasts during Ramadan with faith and seeking reward..."}],
        },
        'general_islamic': {
            "quran_references": [{"surah": "Al-Baqarah", "verse": 2,
                                   "text": "This is the Book about which there is no doubt..."}],
            "hadith_references": [{"source": "Muslim", "number": 2588,
                                    "text": "The best of you are those with the best character."}],
        },
    }

    def research(self, topic: str, theme: str) -> Dict:
        # NEW (Module 6): AI Settings prompt template (lazy import — see
        # planner.py for why). Default text is byte-for-byte the original.
        from holy_month.services.prompt_templates import render
        prompt = render("research", topic=topic, theme=theme)
        result = gemini_json(prompt)
        if result and isinstance(result, dict) and result.get("quran_references"):
            result["topic"] = topic
            result["theme"] = theme
            result["_source"] = "gemini"  # flagged for the human reviewer's benefit
            return result

        print(f"⚠️  Research: Gemini unavailable for '{topic}' — using theme-level fallback (less specific).")
        fallback = self._FALLBACK.get(theme.lower(), self._FALLBACK['general_islamic'])
        return {
            "topic": topic, "theme": theme, "_source": "fallback",
            "quran_references": fallback["quran_references"],
            "hadith_references": fallback["hadith_references"],
            "historical_facts": ["Islamic history is rich with events related to this topic."],
            "keywords": [topic, theme, "Islamic", "Muslim", "faith", "guidance"],
            "audience_interest": "Learning about Islamic teachings and applying them in daily life",
        }
