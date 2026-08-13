import os
from typing import Dict, List, Optional

import edge_tts

from holy_month.utils import get_audio_duration_seconds


class VoiceAgent:
    """Generates ONE clip PER SCENE (not one giant narration blob), so
    each scene's real spoken duration is known exactly via ffprobe —
    that's what makes exact per-scene video-duration matching possible
    in the assembly step."""

    VOICES = {
        'en': 'en-US-AriaNeural',
        'en-male': 'en-US-GuyNeural',
        'ar': 'ar-EG-SalmaNeural',
        'ur': 'ur-PK-AsadNeural',
    }

    async def generate_voice_clip(self, text: str, language: str, out_path: str) -> Optional[str]:
        try:
            voice = self.VOICES.get(language, self.VOICES['en'])
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(out_path)
            return out_path
        except Exception as e:
            print(f"Voice generation error: {e}")
            return None

    async def generate_scene_voices(self, scenes_text: List[str], language: str, work_dir: str) -> List[Dict]:
        """Returns a list of {"text", "audio_path", "duration"} — None
        entries for any scene whose TTS failed, so callers can skip/flag it."""
        results = []
        for i, text in enumerate(scenes_text):
            out_path = os.path.join(work_dir, f"scene_{i:02d}_voice.mp3")
            path = await self.generate_voice_clip(text, language, out_path)
            duration = get_audio_duration_seconds(path) if path else 0.0
            results.append({"text": text, "audio_path": path, "duration": duration})
        return results
