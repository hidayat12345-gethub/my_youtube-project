# Module 1 — Backend Split + 20h Auto-Approval

## What changed

**Nothing functional changed except the one thing you asked for.** Every
agent, route, and pipeline step is the same code, moved into its own file.
`daily-video.yml` needs zero edits — it still calls
`python holy_month_automation.py produce-today`, which now just delegates
into the `holy_month/` package.

## New behavior: 20-hour auto-approval

- `.env` gains `AUTO_APPROVE_AFTER_HOURS=20` (set to `0` to disable).
- `Video.uploaded_at` — a column that existed before but was never
  written to — is now set the moment a video uploads as unlisted.
- `holy_month/services/auto_approval.py` is new: it finds any video
  still `pending_review` past that window and calls the *same*
  `UploadAgent.make_public()` the manual `/approve` endpoint uses.
- Auto-published videos get `status='auto_published'` (not
  `'published'`) purely so you can tell "a human approved this" apart
  from "the clock ran out" later, in the DB or the dashboard.
- The sweep runs from **two** places, matching your two deployment
  modes:
  - `web` mode: every scheduler cycle (`services/scheduler.py`), independent of `PUBLISH_HOUR`.
  - `produce-today` (GitHub Actions) mode: once per daily run, right after that day's video is produced (`cli.py`), since there's no persistent loop to do it continuously.
- Telegram gets a distinct notice when this fires: *"⏰ Auto-approved
  after 20h (no manual review) — Day X: [title]"*.

## New file layout

```
holy_month_automation.py     entrypoint, backward-compatible with daily-video.yml
holy_month/
  config/settings.py         install_requirements, .env bootstrap, Config
  db/models.py, session.py   MonthlyPlan, Video, engine
  utils.py                   gemini_json, strip_json_fences, ffprobe duration, font loader
  agents/                    one file per agent (planner, research, script_writer,
                              voice, image_gen, thumbnail, assembly, seo,
                              youtube_upload, notify)
  services/
    orchestrator.py          HolyMonthOrchestrator.produce_video() — the 9-step pipeline
    production.py            produce_single_video() + "what's due today" queries
    auto_approval.py         NEW — the 20h sweep
    scheduler.py             daily_scheduler_loop() (web mode)
  api/
    schemas.py                Pydantic request/response models
    routes_system.py          /, /health, /api/v1/status
    routes_plans.py           monthly-plan, plans list/detail (NEW), produce-next, pause/resume
    routes_videos.py          approve, reject (NEW), videos list, video detail (NEW)
  main.py                    FastAPI app factory (CORS, routers, scheduler startup)
  cli.py                     youtube-auth / create-plan / produce-today / web / test
```

Every endpoint that existed before still exists at the same path. Added
endpoints (`GET /api/v1/plans`, `GET /api/v1/plans/{id}`,
`GET /api/v1/videos/{id}`, `POST /api/v1/videos/{id}/reject`) are there
because the dashboard (Module 2) needs them — none of them change
existing behavior.

## What I did NOT do yet (waiting for your go-ahead)

- No Streamlit code yet.
- Didn't touch `daily-video.yml` — it doesn't need changes, but if you
  want it to also install `pydantic-settings`/etc. explicitly instead
  of relying on `requirements.txt`, say so and I'll sync it.
- Didn't add the YouTube Analytics sync job (subscribers/watch time)
  yet — that's Analytics-page-specific work, coming with that module.

## How to verify locally before merging into your repo

```bash
pip install -r requirements.txt --break-system-packages
python holy_month_automation.py web        # sanity check the server boots
# or, non-interactively:
PLAN_THEME=ramadan PLAN_HOLY_MONTH=Ramadan PLAN_AUDIENCE="young adults" \
  python holy_month_automation.py create-plan
python holy_month_automation.py produce-today
```

All new files pass `python -m py_compile` (syntax-checked). I couldn't
run a live import/integration test in this environment since it has no
network access to install `fastapi`/`sqlalchemy`/etc. — worth running
the commands above once locally before you commit.
