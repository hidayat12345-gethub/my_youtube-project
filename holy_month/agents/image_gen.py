import os
import urllib.parse
from typing import List

import requests
from PIL import Image, ImageDraw

from holy_month.utils import load_font


class ImageGenerationAgent:
    """Calls Pollinations.ai (free, no API key) to generate a real image
    per scene. The drawn-text-card is kept ONLY as a fallback for when
    the network call fails, not as the primary output."""

    POLLINATIONS_BASE = "https://image.pollinations.ai/prompt/"

    def _build_visual_prompt(self, scene_text: str, theme: str) -> str:
        """Turn a narration paragraph into a concrete visual prompt —
        Pollinations (Stable Diffusion-family backend) needs a scene
        description, not narration text verbatim."""
        snippet = scene_text.strip()[:200]
        return (f"cinematic, respectful, non-figurative Islamic art style illustration "
                f"representing: {snippet}. Theme: {theme}. Warm golden lighting, "
                f"geometric Islamic patterns, mosque architecture, calligraphy accents, "
                f"no text, no human faces, peaceful atmosphere, 4k, highly detailed")

    def generate_scene_image(self, scene_text: str, theme: str, out_path: str) -> str:
        prompt = self._build_visual_prompt(scene_text, theme)
        url = self.POLLINATIONS_BASE + urllib.parse.quote(prompt) + "?width=1920&height=1080&nologo=true"
        try:
            resp = requests.get(url, timeout=90)
            resp.raise_for_status()
            with open(out_path, 'wb') as f:
                f.write(resp.content)
            return out_path
        except Exception as e:
            print(f"⚠️  Pollinations image generation failed ({e}) — using text-card fallback.")
            return self._fallback_text_card(scene_text, out_path)

    def _fallback_text_card(self, text: str, out_path: str) -> str:
        img = Image.new('RGB', (1920, 1080), color=(13, 27, 42))
        draw = ImageDraw.Draw(img)
        font = load_font(40)

        snippet = text[:200]
        bbox = draw.textbbox((0, 0), snippet, font=font)
        x = (1920 - (bbox[2] - bbox[0])) // 2
        y = (1080 - (bbox[3] - bbox[1])) // 2
        draw.text((x + 2, y + 2), snippet, fill=(0, 0, 0), font=font)
        draw.text((x, y), snippet, fill=(255, 255, 255), font=font)
        draw.rectangle([(10, 10), (1910, 1070)], outline=(255, 215, 0), width=5)

        img.save(out_path)
        return out_path

    def generate_scenes(self, scenes_text: List[str], theme: str, work_dir: str) -> List[str]:
        paths = []
        for i, text in enumerate(scenes_text):
            out_path = os.path.join(work_dir, f"scene_{i:02d}_image.jpg")
            paths.append(self.generate_scene_image(text, theme, out_path))
        return paths
