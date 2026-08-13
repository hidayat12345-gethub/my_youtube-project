# Holy Month AI

Automated Islamic educational YouTube video pipeline + a Streamlit control dashboard,
built on 100% free-tier services (Gemini, edge-tts, Pollinations.ai, ffmpeg, YouTube's
free API quota).

## Project structure

```
holy_month_automation.py     Entrypoint — same CLI your GitHub Actions workflow already calls
requirements.txt             Backend dependencies
daily-video.yml              GitHub Actions workflow (goes in .github/workflows/)
holy_month.db                SQLite database (your existing data — keep it)

holy_month/                  Backend package
  config/                    .env bootstrap, Config
  db/                        SQLAlchemy models (MonthlyPlan, Video)
  utils.py                   Shared helpers (Gemini calls, ffprobe, fonts)
  agents/                    One file per pipeline step (planner, research, script,
                              voice, images, thumbnail, assembly, SEO, upload, notify)
  services/                  Orchestration: the 9-step pipeline, scheduler, auto-approval
                              sweep, video editor regeneration, YouTube stats sync,
                              settings/prompt-template stores, system admin (backup/cleanup)
  api/                       FastAPI routes (plans, videos, system, youtube, settings)
  main.py                    FastAPI app factory
  cli.py                     youtube-auth / create-plan / produce-today / web / test
  logging_setup.py           Captures print() output to logs/holy_month.log

dashboard/                   Streamlit control panel
  Home.py                    Entrypoint — run with `streamlit run dashboard/Home.py`
  pages/                     Dashboard, Video Manager, Review Center, Monthly Planner,
                              Analytics, YouTube, AI Settings, System Settings, Logs, About
  db_reader.py                Direct SQLite reads (works without a live backend)
  api_client.py                Talks to the FastAPI backend for live actions
  logs_reader.py               Local log file reader
  style.py                     Shared dark theme / CSS
  requirements-dashboard.txt   Lighter dependency set than the backend

MODULE_1_NOTES.md ... MODULE_6_NOTES.md    What shipped in each build phase, and why
```

## Setup

```bash
# Backend
cp .env.example .env        # then fill in your real keys — .env is gitignored
pip install -r requirements.txt --break-system-packages
python holy_month_automation.py youtube-auth     # one-time OAuth setup
python holy_month_automation.py create-plan       # one-time: plan this month's videos

# Dashboard (separate terminal, or separate machine)
pip install -r dashboard/requirements-dashboard.txt --break-system-packages
streamlit run dashboard/Home.py
```

## Testing

```bash
pip install -r requirements-dev.txt --break-system-packages
pytest tests/ -v
```

Every test runs in an isolated temp directory with a fake `.env` and a throwaway SQLite database — never your real `.env` or `holy_month.db`, and nothing makes a real Gemini/YouTube/Telegram call (those are mocked). See `AUDIT_REPORT.md` for what's covered and what isn't.

## Docker (optional)

Local use needs no Docker at all (see Setup above). If you want to run this on a Linux host/VPS instead:
```bash
cp .env.example .env   # fill in real values
docker compose up --build
```

## Security

By default this is a localhost, single-operator tool with no authentication — matches "don't add unnecessary auth complexity" for that use case. If you ever expose the backend beyond your own machine, set `API_ACCESS_TOKEN` in `.env` (and `ALLOWED_ORIGINS` if the dashboard runs somewhere other than the default local Streamlit ports) — see `.env.example` and `AUDIT_REPORT.md`.


## Two ways to run the pipeline day-to-day

**GitHub Actions (free, no owned machine)** — `daily-video.yml` runs `produce-today`
once a day on GitHub's own servers and commits `holy_month.db` back to the repo.
The dashboard works against this in **read-only mode**: it reads `holy_month.db`
directly, no server required, but Approve/Reject/Edit/Regenerate buttons are disabled
since those need to actually call Gemini/YouTube/ffmpeg live.

**`web` mode (a machine that stays on)** — `python holy_month_automation.py web` runs
a persistent FastAPI server with its own scheduler. The dashboard auto-detects it at
`http://localhost:8000` (override with `HOLY_MONTH_API_URL`) and unlocks every live
action.

You can run both — GitHub Actions as the reliable daily driver, `web` mode locally
whenever you want to actively manage things through the dashboard.

## Before you rely on this with a real month of content

Every file here has been syntax-checked (`python -m py_compile`), but the environment
this was built in had no network access to actually install and run
FastAPI/Streamlit/edge-tts/ffmpeg together end to end. Run the verify steps at the
bottom of each `MODULE_*_NOTES.md` file locally first — especially Module 5's
YouTube re-authorization step (a new OAuth scope was added; your existing refresh
token needs to be regenerated once via `youtube-auth`).

## Known limitations (see `dashboard/pages/9_ℹ️_About.py` for the full list)

No background music support, no settable video duration, can't regenerate an
already-published video, no persisted logs for GitHub Actions runs, no
authentication on the API or dashboard. None of these are accidental — each is
explained in the relevant module's notes file.
