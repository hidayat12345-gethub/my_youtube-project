# Module 4 — Video Editor

## Backend — new files/endpoints, all additive

`holy_month/services/video_editor.py` (new file):
- `regenerate_video(video_id, voice, language_override)` — re-renders voice + images + video from the video's stored (possibly edited) script, deletes the old unlisted YouTube upload if one exists, and re-uploads.
- `regenerate_thumbnail(video_id)` — regenerates just the thumbnail; pushes it to YouTube via `thumbnails().set()` if already uploaded.

`holy_month/api/routes_videos.py` — 4 new endpoints:

| Endpoint | What it does |
|---|---|
| `PUT /api/v1/videos/{id}/metadata` | Edit title/description/tags/hashtags. Works on any status. |
| `PUT /api/v1/videos/{id}/script` | Save an edited script (hook/intro/body/ending/cta) to the DB. Does **not** regenerate the video by itself. |
| `POST /api/v1/videos/{id}/regenerate-thumbnail` | New thumbnail, works even on published videos. |
| `POST /api/v1/videos/{id}/regenerate` | Full re-render from the stored script. **Blocked for already-published videos** — see below. |

## An important limitation I didn't paper over

**You can't regenerate an already-published video.** YouTube's API has no "replace this video's footage" operation — the only way to change what's actually playing is delete + re-upload, which breaks any link/embed/notification that already went out for a public video. So `regenerate` only works while status is `pending_review`, `rejected`, `failed`, or `saved_locally`. If you need to fix something on a published video, editing metadata (always available) or producing a fresh video for a later day are the real options.

**Also not implemented: background music and a settable video duration.** The pipeline has no audio-mixing step at all, and no global duration control — each scene's length comes from how long its own TTS narration runs, not a number you set. I didn't add fake sliders that don't actually do anything; the Video Editor UI says so directly instead of pretending.

## Dashboard changes

`dashboard/style.py` — added `REGENERATABLE_STATUSES`, mirroring the backend's set (kept as a duplicate constant rather than an import, since the dashboard is deliberately kept independent of the backend's dependency chain — see `dashboard/README.md`).

`dashboard/api_client.py` — `update_video_metadata`, `update_video_script`, `regenerate_video_thumbnail`, `regenerate_video_full` (the last one has a 10-minute timeout — a full regenerate does real TTS + image generation + ffmpeg assembly + upload, and can genuinely take a few minutes on a multi-scene video).

`dashboard/pages/1_🎥_Video_Manager.py` — every video row now has an **"✏️ Open Video Editor"** toggle that expands a three-tab panel:
- **📝 Metadata** — title/description/tags/hashtags, save-only
- **📜 Script** — hook/introduction/body (one scene per line)/ending/CTA, save-only
- **🔁 Regenerate & Thumbnail** — voice picker (mirrors `VoiceAgent.VOICES`), optional language override, the regenerate button (disabled for published videos, with an explanation), and thumbnail regeneration (always available)

I built this inline within Video Manager rather than as a separate sidebar page — Streamlit's file-based page ordering breaks once you go past single digits without zero-padding all the filenames, and "open any video and edit it" reads more like a detail view than a nav destination anyway.

## Verify locally

```bash
python holy_month_automation.py web
streamlit run dashboard/Home.py
```
Open Video Manager, pick a video with status `saved_locally` or `pending_review` (safest to test regenerate on), open its editor, tweak the script, save, then try Regenerate. Test metadata edits and thumbnail regeneration on a couple of different statuses too.
