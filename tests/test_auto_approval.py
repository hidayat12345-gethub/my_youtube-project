"""20-hour auto-approval sweep tests. Real DB (temp-file SQLite),
mocked UploadAgent/NotificationAgent — no real YouTube or Telegram
calls."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest


def _make_pending_video(db_session, hours_ago: float, youtube_video_id="yt_abc123"):
    from holy_month.db import Video
    video = Video(
        title="Auto-Approval Test Video", status="pending_review",
        youtube_video_id=youtube_video_id, youtube_url=f"https://youtube.com/watch?v={youtube_video_id}",
        uploaded_at=datetime.now() - timedelta(hours=hours_ago), day_index=1,
    )
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    return video.id


def test_video_past_cutoff_gets_auto_published(db_session):
    """AUTO_APPROVE_AFTER_HOURS=20 in the test .env — a video uploaded
    21 hours ago is overdue."""
    video_id = _make_pending_video(db_session, hours_ago=21)

    with patch("holy_month.services.auto_approval.UploadAgent") as MockUploadAgent, \
         patch("holy_month.services.auto_approval.NotificationAgent") as MockNotifier:
        MockUploadAgent.return_value.make_public.return_value = True
        from holy_month.services.auto_approval import run_auto_approval_sweep
        result = run_auto_approval_sweep()

    assert video_id in result

    from holy_month.db import Video
    reloaded = db_session.query(Video).filter(Video.id == video_id).first()
    assert reloaded.status == "auto_published"
    MockNotifier.return_value.send_telegram.assert_called_once()


def test_video_within_window_is_left_alone(db_session):
    """Uploaded 2 hours ago, window is 20h — should NOT be touched."""
    video_id = _make_pending_video(db_session, hours_ago=2)

    with patch("holy_month.services.auto_approval.UploadAgent") as MockUploadAgent:
        MockUploadAgent.return_value.make_public.return_value = True
        from holy_month.services.auto_approval import run_auto_approval_sweep
        result = run_auto_approval_sweep()

    assert video_id not in result

    from holy_month.db import Video
    reloaded = db_session.query(Video).filter(Video.id == video_id).first()
    assert reloaded.status == "pending_review"  # untouched


def test_video_without_youtube_id_is_skipped(db_session):
    """A video that failed to upload (saved_locally, no youtube_video_id)
    should never be swept even if it's technically 'pending_review' —
    there's nothing to make_public()."""
    video_id = _make_pending_video(db_session, hours_ago=25, youtube_video_id=None)

    with patch("holy_month.services.auto_approval.UploadAgent") as MockUploadAgent:
        MockUploadAgent.return_value.make_public.return_value = True
        from holy_month.services.auto_approval import run_auto_approval_sweep
        result = run_auto_approval_sweep()

    assert video_id not in result


def test_failed_publish_leaves_video_pending_for_retry(db_session):
    """If make_public() fails (YouTube API error), the video should
    stay pending_review so the NEXT sweep retries it — not get marked
    auto_published on a failed call, and not get stuck in a broken
    state either."""
    video_id = _make_pending_video(db_session, hours_ago=25)

    with patch("holy_month.services.auto_approval.UploadAgent") as MockUploadAgent, \
         patch("holy_month.services.auto_approval.NotificationAgent"):
        MockUploadAgent.return_value.make_public.return_value = False
        from holy_month.services.auto_approval import run_auto_approval_sweep
        result = run_auto_approval_sweep()

    assert video_id not in result  # not counted as successfully auto-published

    from holy_month.db import Video
    reloaded = db_session.query(Video).filter(Video.id == video_id).first()
    assert reloaded.status == "pending_review"  # still there for the next sweep to retry


def test_sweep_disabled_when_auto_approve_hours_is_zero(db_session, monkeypatch):
    video_id = _make_pending_video(db_session, hours_ago=100)

    from holy_month.config import Config
    monkeypatch.setattr(Config, "AUTO_APPROVE_AFTER_HOURS", 0)

    from holy_month.services.auto_approval import run_auto_approval_sweep
    result = run_auto_approval_sweep()

    assert result == []
