import os
import subprocess
from datetime import datetime
from typing import Dict, List, Optional

from holy_month.config import Config


class VideoAssemblyAgent:
    def __init__(self):
        self.ffmpeg_available = self.check_ffmpeg()

    def check_ffmpeg(self) -> bool:
        """FIX (audit): previously only printed a warning at construction
        time and then proceeded anyway — a truly missing ffmpeg would
        surface later as a raw, unhelpful FileNotFoundError buried deep
        in a subprocess call. Now returns a real flag assemble_video()
        checks up front, so a missing ffmpeg fails immediately with the
        same clear, actionable message instead of an unpredictable
        failure a few steps into assembly."""
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True)
            return True
        except FileNotFoundError:
            print("⚠️  FFmpeg not found! Install it: 'sudo apt install ffmpeg' (Ubuntu), "
                  "'brew install ffmpeg' (Mac), or on Windows download a build from "
                  "https://ffmpeg.org/download.html and add its bin/ folder to your PATH "
                  "(System Properties > Environment Variables > Path). Restart your terminal "
                  "after adding it, then verify with 'ffmpeg -version'.")
            return False

    def _run(self, cmd: List[str]):
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr[-1500:]}")

    def _format_srt_timestamp(self, seconds: float) -> str:
        ms = int(round((seconds - int(seconds)) * 1000))
        s = int(seconds) % 60
        m = (int(seconds) // 60) % 60
        h = int(seconds) // 3600
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def build_srt(self, scenes: List[Dict], out_path: str) -> None:
        """Subtitles, using the REAL per-scene durations."""
        lines, t = [], 0.0
        for i, scene in enumerate(scenes, start=1):
            duration = scene["duration"] or 5.0
            lines += [str(i),
                      f"{self._format_srt_timestamp(t)} --> {self._format_srt_timestamp(t + duration)}",
                      scene["text"].strip(), ""]
            t += duration
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))

    def assemble_video(self, scenes: List[Dict], theme_title: str, work_dir: str) -> Optional[str]:
        """
        scenes: list of {"text", "audio_path", "duration", "image_path"}.
        Each scene's clip is built to EXACTLY match that scene's real
        narration duration (via ffprobe earlier), instead of a fixed
        seconds/scene number that could silently truncate narration.
        """
        # FIX (audit): fail fast and clearly instead of letting a
        # missing ffmpeg surface as a confusing subprocess error partway
        # through assembly.
        if not self.ffmpeg_available:
            print("❌ Can't assemble video: ffmpeg is not installed or not on PATH. See the "
                  "warning printed at startup for install instructions.")
            return None

        valid_scenes = [s for s in scenes if s.get("audio_path") and s.get("image_path")]
        if not valid_scenes:
            print("No valid scenes to assemble (voice or image generation failed for all of them)")
            return None

        try:
            clip_paths = []
            for i, scene in enumerate(valid_scenes):
                clip_path = os.path.join(work_dir, f"clip_{i:02d}.mp4")
                duration = max(scene["duration"], 1.0)
                self._run([
                    'ffmpeg', '-y', '-loglevel', 'error',
                    '-loop', '1', '-i', scene["image_path"],
                    '-i', scene["audio_path"],
                    '-t', str(duration),
                    '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,'
                           'pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p',
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                    '-c:a', 'aac', '-b:a', '192k',
                    '-shortest',
                    clip_path,
                ])
                clip_paths.append(clip_path)

            concat_list_path = os.path.join(work_dir, "concat_list.txt")
            with open(concat_list_path, 'w') as f:
                for p in clip_paths:
                    f.write(f"file '{os.path.abspath(p)}'\n")

            concatenated_path = os.path.join(work_dir, "concatenated.mp4")
            self._run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0',
                       '-i', concat_list_path, '-c', 'copy', concatenated_path])

            srt_path = os.path.join(work_dir, "subtitles.srt")
            self.build_srt(valid_scenes, srt_path)

            output_file = os.path.join(Config.OUTPUT_DIR, f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
            # FIX (audit): on Windows, srt_path contains backslashes
            # (e.g. C:\Users\...\subtitles.srt). ffmpeg's filtergraph
            # parser uses backslash as its own escape character, so a
            # raw Windows path breaks the subtitles filter — not just
            # the drive-letter colon. ffmpeg accepts forward slashes on
            # Windows too, so normalizing separators first (in addition
            # to the existing colon-escape) fixes subtitle burn-in on
            # Windows without needing any platform-specific branching.
            escaped_srt = srt_path.replace("\\", "/").replace(":", "\\:")
            # NEW (Module 6): caption size is now AI Settings-configurable
            # (lazy import — same circular-import reasoning as thumbnail.py).
            from holy_month.services.settings_store import get_setting
            caption_font_size = int(get_setting("caption_font_size") or 20)
            self._run(['ffmpeg', '-y', '-loglevel', 'error', '-i', concatenated_path,
                       '-vf', f"subtitles='{escaped_srt}':force_style='FontSize={caption_font_size},Outline=1,Shadow=0'",
                       '-c:a', 'copy', output_file])

            return output_file

        except Exception as e:
            print(f"Assembly error: {e}")
            return self._create_placeholder_video(theme_title)

    def _create_placeholder_video(self, title: str) -> Optional[str]:
        output_file = os.path.join(Config.OUTPUT_DIR, f"placeholder_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
        # FIX (audit): title can be AI-generated or user-edited (Video
        # Editor script title) and was interpolated directly into an
        # ffmpeg filter string — a title containing a single quote or
        # colon would break the filter syntax and fail the placeholder
        # generation too (no shell=True is used anywhere, so this was
        # never a command-injection risk, just a robustness bug: ffmpeg
        # filtergraph syntax, not a shell, was what could break).
        safe_title = (title or "Video").replace("\\", "").replace("'", "").replace(":", " -")[:100]
        try:
            self._run([
                'ffmpeg', '-y', '-loglevel', 'error',
                '-f', 'lavfi', '-i', 'color=c=black:s=1920x1080:d=60',
                '-vf', f"drawtext=text='{safe_title}':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2",
                '-c:v', 'libx264', '-t', '60', output_file,
            ])
            return output_file
        except Exception:
            return None
