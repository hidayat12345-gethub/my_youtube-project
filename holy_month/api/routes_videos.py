import json

from fastapi import APIRouter, HTTPException, Depends

from holy_month.db import SessionLocal, Video
from holy_month.agents import UploadAgent
from holy_month.services.video_editor import regenerate_video, regenerate_thumbnail, REGENERATABLE_STATUSES
from .schemas import VideoResponse, VideoMetadataUpdate, VideoScriptUpdate, VideoRegenerateRequest, AIDisclosureUpdate
from .security import verify_api_key

# FIX (audit): see routes_plans.py — same router-level auth pattern.
router = APIRouter(prefix="/api/v1", tags=["videos"], dependencies=[Depends(verify_api_key)])


@router.post("/videos/{video_id}/approve")
async def approve_video(video_id: int):
    """The human-review gate. Videos upload as UNLISTED (see
    UploadAgent); calling this makes one public. (The 20h
    auto-approval sweep calls the same UploadAgent.make_public() but
    tags the result 'auto_published' instead, so this manual path is
    unchanged.)"""
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(404, "Video not found")
        if video.status != "pending_review":
            raise HTTPException(400, f"Video is not pending review (status={video.status})")
        if not video.youtube_video_id:
            raise HTTPException(400, "Video has no YouTube ID (was it saved locally instead of uploaded?)")

        upload_agent = UploadAgent()
        ok = upload_agent.make_public(video.youtube_video_id)
        if not ok:
            raise HTTPException(500, "Failed to make video public — check YouTube auth")

        video.status = "published"
        db.commit()
    finally:
        db.close()
    return {"video_id": video_id, "status": "published"}


@router.post("/videos/{video_id}/reject")
async def reject_video(video_id: int):
    """NEW — Review Center needs a reject action, not just approve.
    Rejecting does not delete the YouTube upload (it stays unlisted);
    it just marks the DB row so the dashboard stops counting it as
    pending and excludes it from the auto-approval sweep (which only
    ever looks at status == 'pending_review')."""
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(404, "Video not found")
        if video.status != "pending_review":
            raise HTTPException(400, f"Video is not pending review (status={video.status})")
        video.status = "rejected"
        db.commit()
    finally:
        db.close()
    return {"video_id": video_id, "status": "rejected"}


@router.get("/videos")
async def get_videos():
    db = SessionLocal()
    try:
        videos = db.query(Video).order_by(Video.created_at.desc()).all()
        return [VideoResponse(id=v.id, title=v.title, status=v.status, day_index=v.day_index,
                               youtube_url=v.youtube_url, created_at=v.created_at,
                               ai_disclosure=v.ai_disclosure or "not_selected") for v in videos]
    finally:
        db.close()


@router.get("/videos/{video_id}")
async def get_video(video_id: int):
    """NEW — full detail for a single video (Video Manager row expand /
    Video Editor / Review Center need more than the list view gives)."""
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(404, "Video not found")
        return {
            "id": video.id, "plan_id": video.plan_id, "day_index": video.day_index,
            "title": video.title, "description": video.description, "status": video.status,
            "script": video.script, "tags": video.tags, "hashtags": video.hashtags,
            "video_path": video.video_path, "thumbnail_path": video.thumbnail_path,
            "youtube_video_id": video.youtube_video_id, "youtube_url": video.youtube_url,
            "views": video.views, "likes": video.likes, "ctr": video.ctr,
            "ai_disclosure": video.ai_disclosure or "not_selected",
            "created_at": video.created_at.isoformat() if video.created_at else None,
            "uploaded_at": video.uploaded_at.isoformat() if video.uploaded_at else None,
        }
    finally:
        db.close()


# ============================================================
# NEW (Module 4) — Video Editor
# ============================================================

@router.put("/videos/{video_id}/metadata")
async def update_video_metadata(video_id: int, update: VideoMetadataUpdate):
    """Edits title/description/tags/hashtags directly. Works regardless
    of status (including already-published videos) — but note this
    only updates the DB row; if the video is already uploaded to
    YouTube, push the same change there via the YouTube Studio app (a
    metadata-sync-to-YouTube endpoint is straightforward to add later
    if you want this dashboard to be the single source of truth for
    published metadata too)."""
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(404, "Video not found")
        if update.title is not None:
            video.title = update.title
        if update.description is not None:
            video.description = update.description
        if update.tags is not None:
            video.tags = update.tags
        if update.hashtags is not None:
            video.hashtags = update.hashtags
        db.commit()
        return {"status": "success", "video_id": video_id}
    finally:
        db.close()


@router.put("/videos/{video_id}/ai-disclosure")
async def set_ai_disclosure(video_id: int, update: AIDisclosureUpdate):
    """NEW (audit) — the user's explicit YouTube Altered/Synthetic
    content disclosure choice. Deliberately separate from 'AI
    Generated' status (which is just always-true for this pipeline's
    output) — this is a publishing/compliance decision the human makes,
    not something inferred automatically.

    Flow: Dashboard -> this endpoint -> DB (always) -> YouTube API
    (only if the video is already uploaded AND the choice is 'yes' or
    'no' — 'not_selected' has nothing meaningful to push, so it's never
    sent to YouTube; the field is simply left unset there rather than
    defaulted to False).

    The DB write and the live YouTube push are reported separately —
    if the video has no youtube_video_id yet, or the live push fails
    (auth issue, quota, network), the DB still reflects the human's
    choice (so it's not lost / doesn't need re-entering), and
    `pushed_to_youtube` tells the caller whether YouTube itself was
    actually updated. Never silently claims a push succeeded when it
    didn't."""
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(404, "Video not found")
        video.ai_disclosure = update.value
        youtube_video_id = video.youtube_video_id
        db.commit()
    finally:
        db.close()

    pushed_to_youtube = False
    push_error = None
    if youtube_video_id and update.value in ("yes", "no"):
        upload_agent = UploadAgent()
        pushed_to_youtube = upload_agent.set_synthetic_media_disclosure(
            youtube_video_id, update.value == "yes")
        if not pushed_to_youtube:
            push_error = ("Saved locally, but couldn't push to YouTube (check auth/quota). "
                          "Will need to be retried.")

    return {"status": "success", "video_id": video_id, "ai_disclosure": update.value,
            "pushed_to_youtube": pushed_to_youtube, "push_error": push_error}


@router.put("/videos/{video_id}/script")
async def update_video_script(video_id: int, update: VideoScriptUpdate):
    """Saves an edited script to the DB. Does NOT regenerate voice/
    images/video by itself — call POST /videos/{id}/regenerate for
    that, once you're happy with the script."""
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(404, "Video not found")
        try:
            script = json.loads(video.script) if video.script else {}
        except json.JSONDecodeError:
            script = {}

        for field, value in update.model_dump(exclude_unset=True).items():
            script[field] = value

        video.script = json.dumps(script)
        db.commit()
        return {"status": "success", "video_id": video_id, "script": script}
    finally:
        db.close()


@router.post("/videos/{video_id}/regenerate-thumbnail")
async def regenerate_video_thumbnail(video_id: int):
    """Regenerates just the thumbnail — works on published videos too,
    since YouTube directly supports replacing a thumbnail (unlike the
    video file itself)."""
    result = await regenerate_thumbnail(video_id)
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    return result


@router.post("/videos/{video_id}/regenerate")
async def regenerate_video_endpoint(video_id: int, req: VideoRegenerateRequest):
    """Re-renders voice + images + video from the (possibly just-edited)
    stored script, deletes the old unlisted YouTube upload if any, and
    uploads the new version fresh. Only allowed while the video is
    still unpublished — see REGENERATABLE_STATUSES and the module
    docstring in services/video_editor.py for why."""
    result = await regenerate_video(video_id, voice=req.voice, language_override=req.language)
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    return result
