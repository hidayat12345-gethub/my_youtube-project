"""NEW MODULE (Video Editor) — regenerate a video's rendered assets
from its (possibly just-edited) stored script, and regenerate just the
thumbnail on its own.

Deliberately narrow about what "editing" can safely mean here:

- Regenerating the full video (voice + images + assembly + re-upload)
  is only allowed while the video is NOT yet public (pending_review,
  rejected, failed, saved_locally). YouTube's API has no "replace this
  video's file" operation — the only way to change a video's actual
  footage is delete + re-upload, which is fine for something nobody's
  seen yet, but would silently orphan a link/embed for anything
  already public. If you need to change a published video, fix the
  metadata (title/description/tags — always editable) or produce a
  fresh video for that day instead.
- Thumbnail regeneration has no such restriction — YouTube directly
  supports replacing a video's thumbnail via thumbnails().set(),
  published or not.
- "Video duration" and "background music volume" from the original
  spec are NOT implemented here: the pipeline has no global duration
  control (each scene's length is derived from its own TTS narration
  time, not a target you can set) and no audio-mixing step at all.
  Rather than fake sliders that do nothing, those controls simply
  aren't exposed — see MODULE_4_NOTES.md.
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Dict, Optional

from holy_month.config import Config
from holy_month.db import SessionLocal, Video, MonthlyPlan
from holy_month.agents import (
    VoiceAgent, ImageGenerationAgent, ThumbnailAgent, VideoAssemblyAgent,
    SEOAgent, UploadAgent, NotificationAgent, get_youtube_client,
)

REGENERATABLE_STATUSES = {"pending_review", "rejected", "failed", "saved_locally"}


def _delete_youtube_video_sync(youtube_video_id: str) -> None:
    try:
        youtube = get_youtube_client()
        youtube.videos().delete(id=youtube_video_id).execute()
    except Exception as e:
        # Best-effort — if this fails the old unlisted video is just
        # left orphaned on the channel, which is a minor cleanup issue,
        # not a reason to fail the whole regenerate operation.
        print(f"⚠️  Couldn't delete old YouTube upload {youtube_video_id}: {e}")


def _set_youtube_thumbnail_sync(youtube_video_id: str, thumbnail_path: str) -> Optional[str]:
    """Returns an error string on failure, or None on success."""
    try:
        from googleapiclient.http import MediaFileUpload
        youtube = get_youtube_client()
        youtube.thumbnails().set(
            videoId=youtube_video_id, media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg"),
        ).execute()
        return None
    except Exception as e:
        return str(e)


async def regenerate_video(video_id: int, voice: str = "en", language_override: Optional[str] = None) -> Dict:
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            return {"ok": False, "error": "Video not found"}
        if video.status not in REGENERATABLE_STATUSES:
            return {"ok": False, "error": (
                f"Can't regenerate a video with status '{video.status}' — only "
                f"{', '.join(sorted(REGENERATABLE_STATUSES))} videos can be regenerated. "
                f"Regenerating an already-public video isn't supported (YouTube has no "
                f"'replace footage' API — only delete+reupload, which would break the "
                f"existing public link)."
            )}
        if not video.script:
            return {"ok": False, "error": "This video has no stored script to regenerate from."}
        script = json.loads(video.script)
        plan = db.query(MonthlyPlan).filter(MonthlyPlan.id == video.plan_id).first() if video.plan_id else None
        theme = plan.theme if plan else "general_islamic"
        language = language_override or (plan.language if plan else "en")
        old_youtube_id = video.youtube_video_id
        day = video.day_index
        # NEW (audit): preserve the human's disclosure choice across
        # regeneration — spec requires this persist through edits/
        # regenerates/retries, not reset to 'not_selected' just because
        # the underlying footage changed.
        existing_disclosure = video.ai_disclosure or "not_selected"
    finally:
        db.close()

    work_dir = os.path.join(Config.OUTPUT_DIR, f"regen_video{video_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}")
    os.makedirs(work_dir, exist_ok=True)

    scene_texts = ([script.get("hook", ""), script.get("introduction", "")]
                   + list(script.get("body", []))
                   + [script.get("ending", ""), script.get("call_to_action", "")])
    scene_texts = [t for t in scene_texts if t and t.strip()]
    if not scene_texts:
        return {"ok": False, "error": "The edited script has no non-empty text — nothing to narrate."}

    voice_agent = VoiceAgent()
    voice_results = await voice_agent.generate_scene_voices(scene_texts, voice, work_dir)

    image_agent = ImageGenerationAgent()
    image_paths = await asyncio.to_thread(image_agent.generate_scenes, scene_texts, theme, work_dir)

    scenes = [
        {"text": t, "audio_path": v["audio_path"], "duration": v["duration"], "image_path": img}
        for t, v, img in zip(scene_texts, voice_results, image_paths)
    ]

    thumbnail_agent = ThumbnailAgent()
    thumbnail_path = await asyncio.to_thread(
        thumbnail_agent.generate_thumbnail, script.get("title", "Video"), theme, work_dir)

    assembly_agent = VideoAssemblyAgent()
    video_path = await asyncio.to_thread(assembly_agent.assemble_video, scenes, script.get("title", "Video"), work_dir)
    if not video_path:
        return {"ok": False, "error": "Video assembly failed — check ffmpeg logs on the server."}

    seo_agent = SEOAgent()
    seo_data = seo_agent.optimize(script, {})

    if old_youtube_id:
        await asyncio.to_thread(_delete_youtube_video_sync, old_youtube_id)

    upload_agent = UploadAgent()
    # NEW (audit): carry the existing disclosure choice into the new
    # upload — None ("not_selected") means don't set the field at all,
    # same "don't silently decide" rule as the original production path.
    disclosure_bool = {"yes": True, "no": False}.get(existing_disclosure)
    upload_result = await asyncio.to_thread(
        upload_agent.upload_video, video_path, seo_data["title"], seo_data["description"],
        seo_data["tags"], thumbnail_path, disclosure_bool,
    )

    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        now = datetime.now()
        new_status = ("pending_review" if upload_result.get("status") == "success" and Config.REQUIRE_HUMAN_REVIEW
                      else "published" if upload_result.get("status") == "success"
                      else "saved_locally")
        video.title = seo_data.get("title", video.title)
        video.description = seo_data.get("description", video.description)
        video.script = json.dumps(script)
        video.tags = seo_data.get("tags", [])
        video.hashtags = seo_data.get("hashtags", [])
        video.video_path = video_path
        video.thumbnail_path = thumbnail_path
        video.youtube_video_id = upload_result.get("video_id", "")
        video.youtube_url = upload_result.get("url", "")
        video.status = new_status
        video.uploaded_at = now if upload_result.get("status") == "success" else None
        video.ai_disclosure = existing_disclosure  # explicitly re-affirmed, not just left alone
        db.commit()
    finally:
        db.close()

    NotificationAgent().send_telegram(
        f"🔁 <b>Video Regenerated</b> — Day {day}: {seo_data.get('title')}\n"
        f"🔗 {upload_result.get('url', '(saved locally — check server output folder)')}"
    )

    return {"ok": True, "status": new_status, "youtube_url": upload_result.get("url", "")}


async def regenerate_thumbnail(video_id: int) -> Dict:
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            return {"ok": False, "error": "Video not found"}
        plan = db.query(MonthlyPlan).filter(MonthlyPlan.id == video.plan_id).first() if video.plan_id else None
        theme = plan.theme if plan else "general_islamic"
        title = video.title
        youtube_video_id = video.youtube_video_id
    finally:
        db.close()

    work_dir = os.path.join(Config.OUTPUT_DIR, f"regen_thumb{video_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}")
    os.makedirs(work_dir, exist_ok=True)
    thumbnail_agent = ThumbnailAgent()
    thumbnail_path = await asyncio.to_thread(thumbnail_agent.generate_thumbnail, title, theme, work_dir)

    if youtube_video_id:
        error = await asyncio.to_thread(_set_youtube_thumbnail_sync, youtube_video_id, thumbnail_path)
        if error:
            return {"ok": False, "error": f"New thumbnail generated but YouTube update failed: {error}"}

    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        video.thumbnail_path = thumbnail_path
        db.commit()
    finally:
        db.close()

    return {"ok": True, "thumbnail_path": thumbnail_path}
