import asyncio
import json
import os
from datetime import datetime
from typing import Dict, Optional

from holy_month.config import Config
from holy_month.db import SessionLocal, Video
from holy_month.agents import (
    ResearchAgent, ScriptWriterAgent, VoiceAgent, ImageGenerationAgent,
    ThumbnailAgent, VideoAssemblyAgent, SEOAgent, UploadAgent, NotificationAgent,
)


class HolyMonthOrchestrator:
    def __init__(self):
        self.research_agent = ResearchAgent()
        self.script_writer = ScriptWriterAgent()
        self.voice_agent = VoiceAgent()
        self.image_agent = ImageGenerationAgent()
        self.thumbnail_agent = ThumbnailAgent()
        self.assembly_agent = VideoAssemblyAgent()
        self.seo_agent = SEOAgent()
        self.upload_agent = UploadAgent()
        self.notifier = NotificationAgent()
        print("🚀 Holy Month AI Factory Ready!")

    async def produce_video(self, theme: str, day: int, title: str, language: str = "en",
                             plan_id: Optional[int] = None) -> Dict:
        print(f"\n{'='*60}\n🎬 Producing Day {day} Video: {title}\n{'='*60}\n")

        result = {"day": day, "title": title, "status": "started", "steps": []}
        work_dir = os.path.join(Config.OUTPUT_DIR, f"work_day{day}_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        os.makedirs(work_dir, exist_ok=True)

        try:
            print("📚 Researching...")
            # research/script/image/thumbnail/assembly/upload are all
            # synchronous blocking calls (network I/O or ffmpeg
            # subprocesses). Running them directly inside this async
            # function would freeze the ENTIRE server's event loop for
            # the full duration of production (can be minutes) - no
            # /health check, no /api/v1/status, and the daily scheduler
            # itself would be stuck too. asyncio.to_thread() runs each
            # one in a background thread instead, keeping the server
            # responsive.
            research = await asyncio.to_thread(self.research_agent.research, title, theme)
            result["steps"].append({"step": 1, "name": "Research", "status": "complete",
                                     "source": research.get("_source", "unknown")})

            print("✍️ Writing script...")
            script = await asyncio.to_thread(self.script_writer.write_script, title, theme, research, "5min")
            result["steps"].append({"step": 2, "name": "Script Writing", "status": "complete"})

            # Scenes are hook+intro+body[]+ending+cta, one TTS clip and
            # one AI image PER scene — not one giant narration blob
            # paired with generic identical images.
            scene_texts = ([script.get("hook", ""), script.get("introduction", "")]
                           + list(script.get("body", []))
                           + [script.get("ending", ""), script.get("call_to_action", "")])
            scene_texts = [t for t in scene_texts if t and t.strip()]

            print(f"🎙️ Generating {len(scene_texts)} voice clips...")
            voice_results = await self.voice_agent.generate_scene_voices(scene_texts, language, work_dir)
            result["steps"].append({"step": 3, "name": "Voice Generation", "status": "complete"})

            print(f"🎨 Generating {len(scene_texts)} scene images...")
            image_paths = await asyncio.to_thread(self.image_agent.generate_scenes, scene_texts, theme, work_dir)
            result["steps"].append({"step": 4, "name": "Scene Generation", "status": "complete"})

            scenes = [
                {"text": t, "audio_path": v["audio_path"], "duration": v["duration"], "image_path": img}
                for t, v, img in zip(scene_texts, voice_results, image_paths)
            ]

            print("🖼️ Generating thumbnail...")
            thumbnail_path = await asyncio.to_thread(
                self.thumbnail_agent.generate_thumbnail, script.get("title", title), theme, work_dir)
            result["steps"].append({"step": 5, "name": "Thumbnail Generation", "status": "complete"})

            print("🔧 Assembling video (per-scene duration matched to narration)...")
            video_path = await asyncio.to_thread(self.assembly_agent.assemble_video, scenes, title, work_dir)
            if not video_path:
                raise RuntimeError("Video assembly failed and placeholder generation also failed.")
            result["steps"].append({"step": 6, "name": "Video Assembly", "status": "complete"})

            print("🔍 Optimizing SEO...")
            seo_data = self.seo_agent.optimize(script, research)
            result["steps"].append({"step": 7, "name": "SEO Optimization", "status": "complete"})

            print("📤 Uploading to YouTube...")
            upload_result = await asyncio.to_thread(
                self.upload_agent.upload_video, video_path, seo_data["title"], seo_data["description"],
                seo_data["tags"], thumbnail_path,
            )
            result["steps"].append({"step": 8, "name": "YouTube Upload", "status": "complete"})

            review_note = ""
            if upload_result.get("status") == "success" and Config.REQUIRE_HUMAN_REVIEW:
                hours = Config.AUTO_APPROVE_AFTER_HOURS
                auto_note = (f"It will auto-approve itself in {hours:g}h if you don't review it first."
                             if hours > 0 else "")
                review_note = (f"\n\n⚠️ <b>Uploaded as UNLISTED — awaiting your review.</b>\n"
                               f"Research source: {research.get('_source')}. If it used the AI research "
                               f"fallback, double-check the Quran/Hadith citations before approving.\n"
                               f"Approve with:\nPOST /api/v1/videos/{{id}}/approve\n{auto_note}")

            print("📱 Sending notification...")
            notification = f"""🌙 <b>Video Ready — Day {day}</b>

📺 Title: {seo_data['title']}
🔗 Link: {upload_result.get('url', 'Check YouTube')}
{review_note}

🕌 <b>Holy Month AI</b>"""
            self.notifier.send_telegram(notification)
            result["steps"].append({"step": 9, "name": "Notification", "status": "complete"})

            result["status"] = "complete"
            result["video_url"] = upload_result.get("url", "")
            result["youtube_video_id"] = upload_result.get("video_id", "")
            result["upload_status"] = upload_result.get("status")

            self._save_to_db(script, video_path, thumbnail_path, upload_result, seo_data, day, plan_id)

            print(f"\n✅ Video Day {day} complete!\n🔗 {result['video_url']}\n")
            return result

        except Exception as e:
            print(f"❌ Production failed: {e}")
            result["status"] = "failed"
            result["error"] = str(e)
            self.notifier.send_telegram(f"❌ <b>Video production failed</b> (Day {day}: {title})\nError: {e}")
            return result

    def _save_to_db(self, script, video_path, thumbnail_path, upload_result, seo_data, day, plan_id=None):
        db = SessionLocal()
        try:
            status = ("pending_review" if upload_result.get("status") == "success" and Config.REQUIRE_HUMAN_REVIEW
                      else "published" if upload_result.get("status") == "success"
                      else "saved_locally")
            now = datetime.now()
            video = Video(
                plan_id=plan_id,
                day_index=day,
                title=seo_data.get('title', ''),
                description=seo_data.get('description', ''),
                script=json.dumps(script),
                status=status,
                publish_date=now,
                video_path=video_path,
                thumbnail_path=thumbnail_path,
                youtube_video_id=upload_result.get('video_id', ''),
                youtube_url=upload_result.get('url', ''),
                tags=seo_data.get('tags', []),
                hashtags=seo_data.get('hashtags', []),
                # NEW: previously this column existed but was never
                # written to, so nothing could ever compute "how long
                # has this been pending_review?" — needed for the
                # AUTO_APPROVE_AFTER_HOURS sweep.
                uploaded_at=now if upload_result.get("status") == "success" else None,
            )
            db.add(video)
            db.commit()
            print("💾 Video saved to database")
        except Exception as e:
            print(f"Database error: {e}")
        finally:
            db.close()
