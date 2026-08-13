"""Video Editor regeneration guard tests.

The important safety property under test: regenerate_video() must
refuse to touch a video that's already public, since YouTube has no
"replace footage" API — only delete+reupload, which would break an
existing public link. This guard check happens before any Gemini/
edge-tts/ffmpeg/YouTube call, so it's testable without mocking any of
that.
"""

import asyncio

import pytest


def _run(coro):
    return asyncio.run(coro)


def test_regeneratable_statuses_are_exactly_the_unpublished_ones():
    from holy_month.services.video_editor import REGENERATABLE_STATUSES
    assert REGENERATABLE_STATUSES == {"pending_review", "rejected", "failed", "saved_locally"}
    assert "published" not in REGENERATABLE_STATUSES
    assert "auto_published" not in REGENERATABLE_STATUSES


@pytest.mark.parametrize("blocked_status", ["published", "auto_published"])
def test_regenerate_refuses_published_video(db_session, blocked_status):
    from holy_month.db import Video
    from holy_month.services.video_editor import regenerate_video

    video = Video(title="Already Public", status=blocked_status,
                  script='{"title": "x", "hook": "y", "body": ["z"]}')
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)

    result = _run(regenerate_video(video.id, voice="en"))

    assert result["ok"] is False
    assert "already-public" in result["error"] or "public" in result["error"].lower()


def test_regenerate_refuses_video_with_no_script(db_session):
    from holy_month.db import Video
    from holy_month.services.video_editor import regenerate_video

    video = Video(title="No Script", status="pending_review", script=None)
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)

    result = _run(regenerate_video(video.id, voice="en"))

    assert result["ok"] is False
    assert "script" in result["error"].lower()


def test_regenerate_refuses_nonexistent_video(db_session):
    from holy_month.services.video_editor import regenerate_video
    result = _run(regenerate_video(999999, voice="en"))
    assert result["ok"] is False
    assert "not found" in result["error"].lower()
