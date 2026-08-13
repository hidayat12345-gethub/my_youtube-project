# Holy Month AI — Dashboard (Module 2)

## Setup

```bash
pip install -r requirements-dashboard.txt --break-system-packages
```

Run from your **repo root** (the same folder as `holy_month.db` and `.env`):

```bash
streamlit run dashboard/Home.py
```

## Two ways it runs

**1. Read-only (default, no server needed)** — works with your existing
GitHub Actions-only deployment. The dashboard reads `holy_month.db`
directly. You can see everything: KPIs, video list, review queue with
live auto-approval countdowns. Approve/Reject buttons are disabled
since those need to actually call the YouTube API.

**2. Live (optional)** — also run the FastAPI backend:

```bash
python holy_month_automation.py web
```

The dashboard auto-detects it at `http://localhost:8000` (override
with the `HOLY_MONTH_API_URL` env var if it's running elsewhere) and
unlocks Approve / Reject buttons in Video Manager and Review Center.

## Pages shipped in this module

- **Dashboard** — KPI cards, service status, status breakdown chart, monthly progress
- **Video Manager** — searchable/filterable table, script/tag preview, approve/reject
- **Review Center** — the human-review queue with a live countdown to each video's
  20-hour auto-approval deadline (mirrors `holy_month/services/auto_approval.py`'s
  cutoff math exactly, so what you see here is what will actually happen)

Every other sidebar item (Monthly Planner, Analytics, YouTube, AI Settings,
System Settings, Logs, About) is a placeholder page explaining what it'll do
and why it's not built yet — so the full navigation exists without faking
data that doesn't exist yet (e.g. Analytics needs a new YouTube stats sync
job in the backend before there's anything real to show).

## Config

Reads the same `.env` your backend uses (no separate config file):
`AUTO_APPROVE_AFTER_HOURS`, `PUBLISH_HOUR`, `REQUIRE_HUMAN_REVIEW`,
plus presence-checks for `GEMINI_API_KEY` / `YOUTUBE_REFRESH_TOKEN` /
`TELEGRAM_BOT_TOKEN`.

If you run the dashboard from a different working directory than the
repo root, set `HOLY_MONTH_DB_PATH=/path/to/holy_month.db`.
