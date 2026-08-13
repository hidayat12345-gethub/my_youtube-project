from typing import Dict, List

from holy_month.utils import gemini_json


class PlannerAgent:
    """Generates video ideas for the month. Asks Gemini (free tier) for
    ideas tailored to the actual theme/audience/language, with the
    hardcoded lists kept ONLY as an emergency fallback if Gemini is
    unavailable - not as the primary source."""

    _FALLBACK_IDEAS = {
        'ramadan': [
            "Introduction to Ramadan - Welcome to the Blessed Month",
            "The Importance of Fasting in Ramadan",
            "Ramadan Quran Reflections - Day 1",
            "How to Prepare for Ramadan Spiritually",
            "The Night of Power - Laylatul Qadr",
            "Zakat and Charity in Ramadan",
            "Ramadan Duas for Forgiveness",
            "The Last 10 Days of Ramadan",
            "Ramadan Daily Routine for Muslims",
            "Breaking Bad Habits in Ramadan",
        ],
        'general_islamic': [
            "The Concept of Tawhid - Oneness of Allah",
            "The Life of Prophet Muhammad (PBUH)",
            "The Importance of Prayer (Salah)",
            "Zakat and Charity in Islam",
            "Fasting in Islam - Beyond Ramadan",
        ],
    }

    def generate_ideas(self, theme: str, holy_month: str, target_audience: str,
                        language: str, count: int = 30) -> List[Dict]:
        # NEW (Module 6): uses the AI Settings prompt template (lazy
        # import to avoid a circular import — services imports agents,
        # which imports this module). Falls back to the exact original
        # hardcoded prompt (now living in prompt_templates.DEFAULTS)
        # unless someone has explicitly edited it in AI Settings.
        from holy_month.services.prompt_templates import render
        prompt = render("planner", count=count, theme=theme, holy_month=holy_month,
                         target_audience=target_audience, language=language)
        result = gemini_json(prompt)
        if result and isinstance(result, list) and len(result) == count:
            return result

        print(f"⚠️  Planner: Gemini didn't return {count} valid ideas — using fallback list.")
        fallback = self._FALLBACK_IDEAS.get(theme.lower(), self._FALLBACK_IDEAS['general_islamic'])
        extended = list(fallback)
        while len(extended) < count:
            extended.extend(fallback)
        return [{"day": i + 1, "title": extended[i], "summary": extended[i]} for i in range(count)]
