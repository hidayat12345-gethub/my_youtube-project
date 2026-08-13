"""NEW MODULE — auto-approval sweep.

Videos upload as UNLISTED and wait for a human to hit /approve. That's
good for catching citation mistakes, but it means the upload cadence
depends on someone being online. This sweep guarantees consistency: if
a video has been sitting in pending_review longer than
Config.AUTO_APPROVE_AFTER_HOURS, it gets published automatically using
the exact same UploadAgent.make_public() call the manual /approve
endpoint uses — nothing new on the YouTube side, just an automatic
trigger for the existing action.

Videos published this way get status='auto_published' (instead of
'published') purely so the dashboard/API can distinguish "a human
looked at this" from "the clock ran out" — no other behavior differs.
"""

from datetime import datetime, timedelta
from typing import List

from holy_month.config import Config
from holy_month.db import SessionLocal, Video
from holy_month.agents import UploadAgent, NotificationAgent


def run_auto_approval_sweep() -> List[int]:
    """Synchronous — safe to call via asyncio.to_thread from the async
    scheduler loop, or directly from the one-shot CLI path. Returns the
    list of video ids that were auto-published this call."""
    if not Config.AUTO_APPROVE_AFTER_HOURS or Config.AUTO_APPROVE_AFTER_HOURS <= 0:
        return []  # sweep disabled

    cutoff = datetime.now() - timedelta(hours=Config.AUTO_APPROVE_AFTER_HOURS)
    upload_agent = UploadAgent()
    notifier = NotificationAgent()
    auto_published_ids = []

    db = SessionLocal()
    try:
        overdue = db.query(Video).filter(
            Video.status == 'pending_review',
            Video.youtube_video_id.isnot(None),
            Video.youtube_video_id != '',
            Video.uploaded_at.isnot(None),
            Video.uploaded_at <= cutoff,
        ).all()

        for video in overdue:
            hours_waited = (datetime.now() - video.uploaded_at).total_seconds() / 3600
            print(f"⏰ Auto-approval: Day {video.day_index} ('{video.title}') has waited "
                  f"{hours_waited:.1f}h with no manual review — publishing now.")

            ok = upload_agent.make_public(video.youtube_video_id)
            if ok:
                video.status = 'auto_published'
                db.commit()
                auto_published_ids.append(video.id)
                notifier.send_telegram(
                    f"⏰ <b>Auto-approved after {Config.AUTO_APPROVE_AFTER_HOURS:g}h</b> "
                    f"(no manual review) — Day {video.day_index}: {video.title}\n"
                    f"🔗 {video.youtube_url}"
                )
            else:
                print(f"⚠️  Auto-approval: failed to publish video {video.id} "
                      f"(youtube_video_id={video.youtube_video_id}) — will retry next sweep.")
    finally:
        db.close()

    return auto_published_ids
