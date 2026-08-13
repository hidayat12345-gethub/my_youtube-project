import os
from typing import Dict, List, Optional

from dotenv import set_key

from holy_month.config import Config, ENV_PATH

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    # NEW (Analytics + YouTube dashboard pages) — watch time / views-over-time
    # come from the separate YouTube Analytics API, which needs its own
    # scope. Subscriber count / total channel views / video view+like+comment
    # counts DON'T need this — they come from the Data API "youtube" scope
    # already above. Existing installs need to re-run `youtube-auth` once to
    # pick this scope up; see MODULE_5_NOTES.md.
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def run_youtube_oauth_setup():
    """One-time interactive OAuth flow. Run via:
    python holy_month_automation.py youtube-auth
    Saves the resulting refresh token straight into .env."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not Config.YOUTUBE_CLIENT_ID or not Config.YOUTUBE_CLIENT_SECRET:
        print("❌ Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env first.")
        print("   Get them free at https://console.cloud.google.com/apis/credentials")
        print("   (Create OAuth Client ID -> Application type: Desktop app)")
        return

    flow = InstalledAppFlow.from_client_config(
        {"installed": {
            "client_id": Config.YOUTUBE_CLIENT_ID,
            "client_secret": Config.YOUTUBE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }},
        scopes=YOUTUBE_SCOPES,
    )
    creds = flow.run_local_server(port=0)
    set_key(ENV_PATH, "YOUTUBE_REFRESH_TOKEN", creds.refresh_token)
    print("✅ YouTube authorized! Refresh token saved to .env automatically.")
    print("   You can now run the app normally: python holy_month_automation.py web")


def get_youtube_client():
    """Real OAuth credentials with the upload scope (a plain API key
    CANNOT perform videos().insert())."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=Config.YOUTUBE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=Config.YOUTUBE_CLIENT_ID,
        client_secret=Config.YOUTUBE_CLIENT_SECRET,
        scopes=YOUTUBE_SCOPES,
    )
    return build("youtube", "v3", credentials=creds)


def get_youtube_analytics_client():
    """NEW — separate API/service from get_youtube_client() above
    ('youtubeAnalytics', not 'youtube'), same OAuth credentials. Powers
    the Analytics page's views/watch-time-over-time charts. Will raise
    (caught by callers) if the current refresh token predates the
    yt-analytics.readonly scope being added — that's the expected
    failure mode for an install that hasn't re-run youtube-auth yet."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=Config.YOUTUBE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=Config.YOUTUBE_CLIENT_ID,
        client_secret=Config.YOUTUBE_CLIENT_SECRET,
        scopes=YOUTUBE_SCOPES,
    )
    return build("youtubeAnalytics", "v2", credentials=creds)


class UploadAgent:
    """Uploads use real OAuth (see get_youtube_client above), and
    default to UNLISTED with a human-approval step before going public
    — see REQUIRE_HUMAN_REVIEW / AUTO_APPROVE_AFTER_HOURS in .env and
    the /approve endpoint plus the auto-approval sweep."""

    def upload_video(self, video_path: str, title: str, description: str,
                      tags: List[str], thumbnail_path: str,
                      contains_synthetic_media: Optional[bool] = None) -> Dict:
        """
        contains_synthetic_media: NEW (audit) — maps directly to
        YouTube's real status.containsSyntheticMedia field (Data API
        v3, added Oct 30 2024, confirmed current as of this build —
        settable on both videos.insert and videos.update). None (the
        default) means "don't set it at upload time" — the human
        hasn't made a disclosure choice yet at initial production time,
        and this project doesn't want to silently decide that for
        them. The disclosure gets set explicitly later via the Review
        Center / Video Editor, through UploadAgent.set_synthetic_media_disclosure().
        """
        print(f"📤 Uploading video: {title}")

        if not Config.YOUTUBE_REFRESH_TOKEN:
            print("⚠️  YouTube not authorized (run 'python holy_month_automation.py youtube-auth'). "
                  "Video saved locally instead.")
            return {"status": "saved_locally", "message": f"Video saved at: {video_path}",
                    "url": f"file://{video_path}"}

        try:
            from googleapiclient.http import MediaFileUpload

            youtube = get_youtube_client()
            privacy = "unlisted" if Config.REQUIRE_HUMAN_REVIEW else "public"

            status_fields = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}
            if contains_synthetic_media is not None:
                status_fields["containsSyntheticMedia"] = contains_synthetic_media

            body = {
                "snippet": {"title": title[:100], "description": description[:5000],
                            "tags": tags[:500], "categoryId": "27"},  # 27 = Education
                "status": status_fields,
            }

            media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
            request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
            response = None
            while response is None:
                _, response = request.next_chunk()
            video_id = response["id"]

            if thumbnail_path and os.path.exists(thumbnail_path):
                try:
                    youtube.thumbnails().set(
                        videoId=video_id, media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg"),
                    ).execute()
                except Exception as e:
                    print(f"Thumbnail upload error: {e}")

            return {"status": "success", "video_id": video_id,
                    "url": f"https://youtube.com/watch?v={video_id}",
                    "privacy": privacy}

        except Exception as e:
            print(f"Upload error: {e}")
            return {"status": "saved_locally", "message": f"Video saved at: {video_path}",
                    "url": f"file://{video_path}", "error": str(e)}

    def set_synthetic_media_disclosure(self, youtube_video_id: str, value: bool) -> bool:
        """NEW (audit) — pushes an Altered/Synthetic content disclosure
        choice to an ALREADY-uploaded video via videos.update. Real
        YouTube Data API v3 field (status.containsSyntheticMedia),
        confirmed current — not invented. Used when a human sets/changes
        the disclosure choice after the video's already live, since
        upload_video() only sets it at initial upload time."""
        try:
            youtube = get_youtube_client()
            youtube.videos().update(
                part="status", body={"id": youtube_video_id, "status": {"containsSyntheticMedia": value}},
            ).execute()
            return True
        except Exception as e:
            print(f"Synthetic media disclosure update error: {e}")
            return False

    def make_public(self, youtube_video_id: str) -> bool:
        """Called by the /approve endpoint (manual) and the auto-approval
        sweep (after AUTO_APPROVE_AFTER_HOURS) once a video is ready to
        go public."""
        try:
            youtube = get_youtube_client()
            youtube.videos().update(
                part="status", body={"id": youtube_video_id, "status": {"privacyStatus": "public"}},
            ).execute()
            return True
        except Exception as e:
            print(f"Approve/publish error: {e}")
            return False
