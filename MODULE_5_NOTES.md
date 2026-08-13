# Module 5 — Analytics + YouTube pages

## ⚠️ Action required: re-run YouTube auth

This module adds the `yt-analytics.readonly` scope (needed for day-by-day
views/watch-time). **Your existing refresh token doesn't have it.** Run:

```bash
python holy_month_automation.py youtube-auth
```

once, and it'll overwrite `YOUTUBE_REFRESH_TOKEN` in `.env` with a token that
has the new scope. Nothing else needs to change. Until you do this, the
Analytics page's views/watch-time chart will show a "re-authorize" message
instead of a raw error — everything else (subscriber count, video stats,
comments, uploads) doesn't need this scope and works immediately.

## Backend — new files

`holy_month/services/youtube_stats.py` (new):
- `sync_video_stats()` — pulls view/like/comment counts for every uploaded video from the Data API (batched, 50 ids/call), writes them to the DB.
- `fetch_channel_summary()` — subscriber count, total channel views, video count.
- `fetch_channel_analytics(days)` — day-by-day views/watch-time/subscribers-gained/likes/comments from the YouTube Analytics API.
- `fetch_recent_comments(max_results)` — latest comment threads across the channel.

`holy_month/api/routes_youtube.py` (new): `POST /api/v1/youtube/sync-stats`, `GET /api/v1/youtube/channel-summary`, `GET /api/v1/youtube/analytics`, `GET /api/v1/youtube/comments`.

`holy_month/agents/youtube_upload.py`: added the new scope, and `get_youtube_analytics_client()` (separate API/service from the existing `get_youtube_client()`).

## Schema change — handled automatically, no data loss

`Video` gets a new `comments` column. Since `Base.metadata.create_all()` only creates missing *tables*, not new *columns* on a table that already exists, I added a small migration check in `holy_month/db/session.py` that runs `ALTER TABLE videos ADD COLUMN comments` the first time it notices the column is missing. Your existing `holy_month.db` and all its video history are untouched — this only adds one new column.

## Stats sync also runs automatically

- **`web` mode**: once per day, right after the daily production check (not every 15-min scheduler cycle — no reason to burn API quota that often).
- **`produce-today` (GitHub Actions)**: once per daily run, right after the auto-approval sweep. Best-effort — if it fails (e.g. you haven't re-authorized yet), it logs a warning and the workflow still succeeds; it doesn't block video production.

## Dashboard — two pages, replacing their stubs

**Analytics** (`pages/4_📊_Analytics.py`):
- Daily/monthly upload counts — from the local DB, works read-only
- Views & watch-time over the last 28 days — **live only**, needs the reauthorized token
- Top 10 videos by views, with likes/comments — reads from the DB (as fresh as the last sync)

**YouTube** (`pages/5_📺_YouTube.py`):
- Channel summary (subscribers/views/video count) + a "🔄 Sync video stats now" button — live only
- Recent uploads — works read-only from the local DB
- Latest comments across the channel — live only

Both pages clearly label which sections need a live backend vs. work from the local DB, same pattern as every other module.

## Verify locally

```bash
python holy_month_automation.py youtube-auth   # re-authorize for the new scope
python holy_month_automation.py web
streamlit run dashboard/Home.py
```
Open YouTube, hit "Sync video stats now", confirm counts show up; open Analytics and confirm the watch-time chart renders (may be empty for a day or two on a very new channel — that's YouTube's own reporting lag, not a bug here).
