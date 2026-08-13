"""NEW MODULE (Module 5) — YouTube stats sync + analytics fetch.

Two different Google APIs are involved, with two different scopes:

- Video view/like/comment counts and channel subscriber/view counts
  come from the youtube "Data API v3" (videos().list, channels().list)
  — covered by the scopes the app already had.
- Day-by-day views / estimated watch time / subscriber deltas come
  from the separate "YouTube Analytics API" (youtubeAnalytics v2),
  which needs the yt-analytics.readonly scope added in Module 5. An
  install that hasn't re-run `youtube-auth` since that scope was added
  will get a 403 here — every function below catches that and returns
  a clear "reauthorize" message instead of crashing, since this is a
  genuinely expected state for existing installs, not a bug.
"""

from datetime import datetime, timedelta
from typing import Dict, List

from holy_month.config import Config
from holy_month.db import SessionLocal, Video
from holy_month.agents import get_youtube_client, get_youtube_analytics_client


def sync_video_stats() -> Dict:
    """Updates views/likes/comments for every video that has a
    youtube_video_id, batching up to 50 ids per Data API call (the
    API's own max) instead of one call per video."""
    if not Config.YOUTUBE_REFRESH_TOKEN:
        return {"ok": False, "error": "YouTube not authorized yet."}

    db = SessionLocal()
    try:
        videos = db.query(Video).filter(
            Video.youtube_video_id.isnot(None), Video.youtube_video_id != ''
        ).all()
        id_to_video = {v.youtube_video_id: v for v in videos}
    finally:
        db.close()

    if not id_to_video:
        return {"ok": True, "updated": 0, "message": "No uploaded videos to sync yet."}

    try:
        youtube = get_youtube_client()
        all_ids = list(id_to_video.keys())
        updated = 0

        db = SessionLocal()
        try:
            for i in range(0, len(all_ids), 50):
                batch_ids = all_ids[i:i + 50]
                response = youtube.videos().list(part="statistics", id=",".join(batch_ids)).execute()
                for item in response.get("items", []):
                    stats = item.get("statistics", {})
                    video = db.query(Video).filter(Video.youtube_video_id == item["id"]).first()
                    if video:
                        video.views = int(stats.get("viewCount", 0))
                        video.likes = int(stats.get("likeCount", 0))
                        video.comments = int(stats.get("commentCount", 0))
                        updated += 1
            db.commit()
        finally:
            db.close()

        return {"ok": True, "updated": updated}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def fetch_channel_summary() -> Dict:
    """Subscriber count, total channel views, video count — Data API,
    no special scope needed beyond what uploading already required."""
    if not Config.YOUTUBE_REFRESH_TOKEN:
        return {"ok": False, "error": "YouTube not authorized yet."}
    try:
        youtube = get_youtube_client()
        response = youtube.channels().list(part="snippet,statistics", mine=True).execute()
        items = response.get("items", [])
        if not items:
            return {"ok": False, "error": "No channel found for this account."}
        channel = items[0]
        stats = channel.get("statistics", {})
        snippet = channel.get("snippet", {})
        return {
            "ok": True,
            "title": snippet.get("title"),
            "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url"),
            "subscriber_count": int(stats.get("subscriberCount", 0)),
            "view_count": int(stats.get("viewCount", 0)),
            "video_count": int(stats.get("videoCount", 0)),
            "hidden_subscriber_count": stats.get("hiddenSubscriberCount", False),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def fetch_recent_comments(max_results: int = 10) -> Dict:
    """Latest comment threads across the whole channel (not per-video)
    — Data API, same scope as everything else here. Channels with
    comments disabled, or a channel with zero comments yet, both come
    back as an empty (not error) result."""
    if not Config.YOUTUBE_REFRESH_TOKEN:
        return {"ok": False, "error": "YouTube not authorized yet."}
    try:
        youtube = get_youtube_client()
        channel_resp = youtube.channels().list(part="id", mine=True).execute()
        channel_items = channel_resp.get("items", [])
        if not channel_items:
            return {"ok": False, "error": "No channel found for this account."}
        channel_id = channel_items[0]["id"]

        resp = youtube.commentThreads().list(
            part="snippet", allThreadsRelatedToChannelId=channel_id,
            order="time", maxResults=max_results, textFormat="plainText",
        ).execute()

        comments = []
        for item in resp.get("items", []):
            top = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "author": top.get("authorDisplayName"),
                "text": top.get("textDisplay", "")[:280],
                "like_count": top.get("likeCount", 0),
                "published_at": top.get("publishedAt"),
                "video_id": item["snippet"].get("videoId"),
            })
        return {"ok": True, "comments": comments}
    except Exception as e:
        msg = str(e)
        if "commentsDisabled" in msg or "disabled" in msg.lower():
            return {"ok": True, "comments": [], "note": "Comments are disabled on one or more videos."}
        return {"ok": False, "error": msg}
    """Day-by-day views/watch-time/subscriber-gained/likes/comments over
    the trailing `days`. Needs yt-analytics.readonly — returns a
    friendly reauthorize message if that scope is missing instead of a
    raw API traceback."""
    if not Config.YOUTUBE_REFRESH_TOKEN:
        return {"ok": False, "error": "YouTube not authorized yet."}
    try:
        analytics = get_youtube_analytics_client()
        end = datetime.now().date()
        start = end - timedelta(days=days)
        response = analytics.reports().query(
            ids="channel==MINE",
            startDate=start.isoformat(),
            endDate=end.isoformat(),
            metrics="views,estimatedMinutesWatched,subscribersGained,likes,comments",
            dimensions="day",
            sort="day",
        ).execute()

        rows: List[Dict] = []
        for row in response.get("rows", []):
            rows.append({
                "date": row[0], "views": row[1], "estimated_minutes_watched": row[2],
                "subscribers_gained": row[3], "likes": row[4], "comments": row[5],
            })
        return {"ok": True, "rows": rows}
    except Exception as e:
        msg = str(e)
        if "403" in msg or "insufficient" in msg.lower() or "forbidden" in msg.lower():
            return {"ok": False, "error": (
                "YouTube Analytics access isn't authorized yet. Re-run "
                "`python holy_month_automation.py youtube-auth` to pick up the "
                "yt-analytics.readonly scope (added in this module), then try again."
            ), "needs_reauth": True}
        return {"ok": False, "error": msg}
