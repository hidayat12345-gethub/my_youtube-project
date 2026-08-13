"""YouTube AI/altered-content disclosure tests.

Covers exactly what the audit spec asked for: Yes/No/Not Selected/
invalid value, DB persistence, API payload generation, upload
behavior, retry behavior. Every YouTube call is mocked — nothing here
makes a real network request or needs real credentials.
"""

from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# Schema validation (Yes / No / Not Selected / invalid)
# ============================================================

def test_disclosure_schema_accepts_yes():
    from holy_month.api.schemas import AIDisclosureUpdate
    assert AIDisclosureUpdate(value="yes").value == "yes"


def test_disclosure_schema_accepts_no():
    from holy_month.api.schemas import AIDisclosureUpdate
    assert AIDisclosureUpdate(value="no").value == "no"


def test_disclosure_schema_accepts_not_selected():
    from holy_month.api.schemas import AIDisclosureUpdate
    assert AIDisclosureUpdate(value="not_selected").value == "not_selected"


def test_disclosure_schema_rejects_invalid_value():
    from holy_month.api.schemas import AIDisclosureUpdate
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        AIDisclosureUpdate(value="maybe")


def test_disclosure_schema_rejects_empty_string():
    from holy_month.api.schemas import AIDisclosureUpdate
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        AIDisclosureUpdate(value="")


# ============================================================
# DB persistence
# ============================================================

def test_disclosure_defaults_to_not_selected_on_new_video(db_session):
    from holy_month.db import Video
    video = Video(title="Disclosure Default Test", status="pending")
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    assert video.ai_disclosure == "not_selected"


def test_disclosure_value_persists_after_update(db_session):
    from holy_month.db import Video
    video = Video(title="Disclosure Persist Test", status="pending_review")
    db_session.add(video)
    db_session.commit()

    video.ai_disclosure = "yes"
    db_session.commit()

    reloaded = db_session.query(Video).filter(Video.id == video.id).first()
    assert reloaded.ai_disclosure == "yes"


# ============================================================
# Upload payload generation (mocked YouTube client)
# ============================================================

def _make_mock_youtube_client(video_id="fake_video_id_123"):
    """Builds a mock that mimics enough of the googleapiclient chain
    for UploadAgent.upload_video()'s videos().insert()...execute()
    call chain, capturing the request body for assertions."""
    mock_youtube = MagicMock()
    mock_insert_request = MagicMock()
    mock_insert_request.next_chunk.return_value = (None, {"id": video_id})
    mock_youtube.videos.return_value.insert.return_value = mock_insert_request
    return mock_youtube


def test_upload_video_sets_synthetic_media_field_when_disclosure_is_true(tmp_path):
    from holy_month.agents.youtube_upload import UploadAgent
    from holy_month.config import Config

    fake_video_path = tmp_path / "fake.mp4"
    fake_video_path.write_bytes(b"not a real video, just bytes for the test")

    mock_youtube = _make_mock_youtube_client()
    with patch("holy_month.agents.youtube_upload.get_youtube_client", return_value=mock_youtube), \
         patch("holy_month.agents.youtube_upload.Config.YOUTUBE_REFRESH_TOKEN", "fake-token-present"), \
         patch("googleapiclient.http.MediaFileUpload"):
        agent = UploadAgent()
        agent.upload_video(str(fake_video_path), "Title", "Description", ["tag1"],
                            "", contains_synthetic_media=True)

    _, kwargs = mock_youtube.videos.return_value.insert.call_args
    assert kwargs["body"]["status"]["containsSyntheticMedia"] is True


def test_upload_video_omits_synthetic_media_field_when_not_selected(tmp_path):
    """The important behavior: 'not selected' means the field is NOT
    sent at all (not defaulted to False) — the project must never
    silently make this compliance decision on the human's behalf."""
    from holy_month.agents.youtube_upload import UploadAgent

    fake_video_path = tmp_path / "fake.mp4"
    fake_video_path.write_bytes(b"fake bytes")

    mock_youtube = _make_mock_youtube_client()
    with patch("holy_month.agents.youtube_upload.get_youtube_client", return_value=mock_youtube), \
         patch("holy_month.agents.youtube_upload.Config.YOUTUBE_REFRESH_TOKEN", "fake-token-present"), \
         patch("googleapiclient.http.MediaFileUpload"):
        agent = UploadAgent()
        agent.upload_video(str(fake_video_path), "Title", "Description", ["tag1"], "",
                            contains_synthetic_media=None)

    _, kwargs = mock_youtube.videos.return_value.insert.call_args
    assert "containsSyntheticMedia" not in kwargs["body"]["status"]


def test_upload_video_sets_false_explicitly_when_disclosure_is_no(tmp_path):
    from holy_month.agents.youtube_upload import UploadAgent

    fake_video_path = tmp_path / "fake.mp4"
    fake_video_path.write_bytes(b"fake bytes")

    mock_youtube = _make_mock_youtube_client()
    with patch("holy_month.agents.youtube_upload.get_youtube_client", return_value=mock_youtube), \
         patch("holy_month.agents.youtube_upload.Config.YOUTUBE_REFRESH_TOKEN", "fake-token-present"), \
         patch("googleapiclient.http.MediaFileUpload"):
        agent = UploadAgent()
        agent.upload_video(str(fake_video_path), "Title", "Description", ["tag1"], "",
                            contains_synthetic_media=False)

    _, kwargs = mock_youtube.videos.return_value.insert.call_args
    assert kwargs["body"]["status"]["containsSyntheticMedia"] is False


def test_upload_video_without_youtube_auth_never_calls_youtube_api():
    """No refresh token configured -> saved_locally, and the YouTube
    client should never even be constructed."""
    from holy_month.agents.youtube_upload import UploadAgent

    with patch("holy_month.agents.youtube_upload.Config.YOUTUBE_REFRESH_TOKEN", ""), \
         patch("holy_month.agents.youtube_upload.get_youtube_client") as mock_get_client:
        agent = UploadAgent()
        result = agent.upload_video("/fake/path.mp4", "Title", "Desc", [], "", contains_synthetic_media=True)

    assert result["status"] == "saved_locally"
    mock_get_client.assert_not_called()


# ============================================================
# set_synthetic_media_disclosure (pushing a change to an already-
# uploaded video) — the "retry behavior" case
# ============================================================

def test_set_synthetic_media_disclosure_success():
    from holy_month.agents.youtube_upload import UploadAgent

    mock_youtube = MagicMock()
    mock_youtube.videos.return_value.update.return_value.execute.return_value = {}

    with patch("holy_month.agents.youtube_upload.get_youtube_client", return_value=mock_youtube):
        agent = UploadAgent()
        ok = agent.set_synthetic_media_disclosure("existing_video_id", True)

    assert ok is True
    _, kwargs = mock_youtube.videos.return_value.update.call_args
    assert kwargs["body"]["status"]["containsSyntheticMedia"] is True
    assert kwargs["body"]["id"] == "existing_video_id"


def test_set_synthetic_media_disclosure_failure_returns_false_not_raise():
    """Retry behavior: a failed push (auth issue, quota, network)
    should surface as a clean False, not an unhandled exception that
    would crash the calling API endpoint."""
    from holy_month.agents.youtube_upload import UploadAgent

    mock_youtube = MagicMock()
    mock_youtube.videos.return_value.update.return_value.execute.side_effect = Exception("quota exceeded")

    with patch("holy_month.agents.youtube_upload.get_youtube_client", return_value=mock_youtube):
        agent = UploadAgent()
        ok = agent.set_synthetic_media_disclosure("existing_video_id", True)

    assert ok is False
