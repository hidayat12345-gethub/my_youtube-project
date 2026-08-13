import os
import urllib.parse

import requests
from PIL import Image, ImageDraw

from holy_month.utils import load_font
from .image_gen import ImageGenerationAgent


class ThumbnailAgent:
    def generate_thumbnail(self, title: str, theme: str, work_dir: str) -> str:
        # NEW (Module 6): text color/size are now AI Settings-configurable
        # (lazy-imported to avoid a circular import — agents are imported
        # BY services, so importing services at module top here would cycle).
        # Defaults match the original hardcoded gold-on-black exactly.
        from holy_month.services.settings_store import get_setting
        text_color = _hex_to_rgb(get_setting("thumbnail_text_color") or "#FFD700")
        font_size = int(get_setting("thumbnail_font_size") or 56)

        # Reuse the same free image generator for a real background,
        # then overlay title text CTR-style on top.
        image_agent = ImageGenerationAgent()
        bg_prompt = image_agent._build_visual_prompt(title, theme)
        bg_url = image_agent.POLLINATIONS_BASE + urllib.parse.quote(bg_prompt) + "?width=1280&height=720&nologo=true"

        img = None
        try:
            resp = requests.get(bg_url, timeout=90)
            resp.raise_for_status()
            bg_path = os.path.join(work_dir, "thumb_bg.jpg")
            with open(bg_path, 'wb') as f:
                f.write(resp.content)
            img = Image.open(bg_path).convert("RGB").resize((1280, 720))
        except Exception as e:
            print(f"⚠️  Thumbnail background generation failed ({e}) — using solid color fallback.")
            img = Image.new('RGB', (1280, 720), color=(13, 27, 42))

        draw = ImageDraw.Draw(img)
        font = load_font(font_size)

        words = title.split()
        lines, current = [], []
        for word in words:
            current.append(word)
            if len(' '.join(current)) > 22:
                lines.append(' '.join(current[:-1]))
                current = [word]
        if current:
            lines.append(' '.join(current))

        line_height = int(font_size * 1.16)
        y = 720 - 80 - (len(lines) * line_height)
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            x = (1280 - (bbox[2] - bbox[0])) // 2
            for dx in (-3, 0, 3):
                for dy in (-3, 0, 3):
                    draw.text((x + dx, y + dy), line, fill=(0, 0, 0), font=font)
            draw.text((x, y), line, fill=text_color, font=font)
            y += line_height

        out_path = os.path.join(work_dir, "thumbnail.jpg")
        img.save(out_path, quality=95)
        return out_path


def _hex_to_rgb(hex_color: str):
    hex_color = (hex_color or "#FFD700").lstrip("#")
    if len(hex_color) != 6:
        return (255, 215, 0)  # fall back to the original gold on any bad input
    try:
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (255, 215, 0)
