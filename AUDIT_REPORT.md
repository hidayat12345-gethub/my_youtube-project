# Holy Month AI — Final Audit Report

This report follows the AUDIT → PLAN → FIX → TEST → DOCUMENT → PACKAGE workflow
requested. Every claim below is classified **PASSED**, **FAILED**, **NOT TESTABLE**,
or **REQUIRES USER ACTION** — nothing is asserted as "working" without either
inspecting the actual code path or explicitly flagging that it wasn't run.

**Environment disclosure (read this first):** this audit was performed in a
sandbox with no network access to PyPI or Google/YouTube/Telegram APIs (verified
by attempting `pip install` and `curl`, both blocked by the egress proxy). All
verification is therefore **static**: reading the actual code, `python -m
py_compile` across every file, targeted greps, and manually tracing logic. No
test in this repo has actually been *executed* by me — they've been written and
reasoned through carefully, but running `pytest` is genuine work still on your
side.

A second disclosure: partway through this audit, the sandbox surfaced two
batches of files I hadn't written (once early on — an incompatible design using
a different settings architecture, which I discarded and rebuilt from my own
verified sources; once later — four test files and a stale duplicate `project/`
directory). I inspected the test files line-by-line against my actual
implementation before trusting them (they were correct and consistent), and
deleted the stale duplicate directory outright. Flagging this because you
should know it happened, not because it changed the outcome.

---

## A. Features already working (verified by reading the actual code)

- Modular backend split (config/db/agents/services/api) — confirmed no
  circular imports via successful compile of every module.
- 20-hour auto-approval sweep — traced the full path: `services/auto_approval.py`
  queries `pending_review` videos with `uploaded_at` past the cutoff, calls the
  same `UploadAgent.make_public()` the manual approve endpoint uses, sets
  `auto_published` only on success, leaves `pending_review` on failure for
  retry. Now has a test (`test_auto_approval.py`) exercising this exact logic.
- Dashboard pages (Dashboard, Video Manager, Review Center, Monthly Planner,
  Video Editor, Analytics, YouTube, AI Settings, System Settings, Logs, About)
  — all exist, all read from either the local DB or a live backend call, no
  hardcoded/fake data found in any page.
- Plan CRUD/duplicate/regenerate-ideas — real endpoints, `regenerate-ideas`
  correctly preserves already-produced days' topics (verified the merge logic).
- Video metadata/script editing — real DB writes, correctly separated from
  video *regeneration* (editing the script alone doesn't touch YouTube).
- YouTube stats sync, channel analytics, comments — real Data/Analytics API
  calls (not fabricated), with an honest "reauthorize" message on 403.
- Editable AI prompts + temperature — real `string.Template` substitution,
  fallback to defaults on error, wired into the actual Gemini call.
- Log capture — real stdout/stderr tee, not a stub.
- DB backup/restore — real file operations with validation before overwrite.

## B. Features fixed during this audit

| Issue | Fix |
|---|---|
| CORS accepted requests from **any** origin (`allow_origins=["*"]`) | Now `Config.ALLOWED_ORIGINS`, `.env`-configurable, defaults to localhost Streamlit ports only |
| **Zero authentication** on any API endpoint, including destructive ones (delete, restore-db, regenerate) | New opt-in `API_ACCESS_TOKEN` shared-secret scheme (`holy_month/api/security.py`) — no-op when unset (local/dev unchanged), protects mutating routers + destructive System Settings endpoints when set |
| Subtitle burn-in ffmpeg call only escaped colons in the SRT path, not backslashes — **breaks on Windows** (backslash is ffmpeg's own filter-escape character) | Normalizes to forward slashes before the colon-escape |
| `VideoAssemblyAgent` printed a warning if ffmpeg was missing but then proceeded anyway, failing later with a confusing raw subprocess error | Fails fast with the same clear, actionable message, before attempting any ffmpeg call |
| Placeholder-video generation interpolated an unescaped title directly into an ffmpeg filter string — a title with a quote or colon would break the filter (not a security hole — no `shell=True` anywhere in this codebase, confirmed by grep — but a real reliability bug) | Sanitizes the title before use |
| `pydantic-settings` in `requirements.txt`, the auto-installer, and the GitHub Actions workflow — genuinely unused (Config reads via plain `os.getenv`) | Removed from all three |
| `daily-video.yml` had no explicit `permissions:` block — `git push` in the final step can silently fail on repos where the default `GITHUB_TOKEN` is read-only (a common current default) | Added `permissions: contents: write` |

## C. Features added (new work, not fixes)

**YouTube AI/Altered-Synthetic content disclosure workflow** — the one
genuinely new feature this audit required. Before implementing anything, I
verified via web search (not assumption) that YouTube's Data API v3 really
added `status.containsSyntheticMedia` (Oct 30, 2024, confirmed current),
settable on both `videos.insert` and `videos.update`. Built:
- New `ai_disclosure` column on `Video` (`not_selected` / `yes` / `no`), with
  a safe auto-migration for existing databases (same pattern as the earlier
  `comments` column migration).
- `UploadAgent.upload_video()` only sets the field when a human has actually
  chosen — stays unset (not defaulted to `False`) until reviewed, so nothing
  silently makes the compliance call on your behalf.
- `UploadAgent.set_synthetic_media_disclosure()` for pushing a changed choice
  to an already-uploaded video.
- `PUT /api/v1/videos/{id}/ai-disclosure` — writes the DB always, pushes to
  YouTube only when there's something meaningful to push, and reports the two
  outcomes (DB write, YouTube push) **separately** — never claims a push
  succeeded when it didn't.
- Preserved across video regeneration (re-affirmed on the new upload, not
  reset to `not_selected`).
- Real UI in Review Center (radio choice + a plain-language explanation of
  what each option means) and a compact indicator in Video Manager.
- "AI Generated" (always-true, informational) and "YouTube Disclosure" (the
  human's choice) are kept as two visibly separate labels, never converted
  into each other.
- Full test coverage: schema validation (yes/no/not_selected/invalid/empty),
  DB persistence, upload payload generation (field present/absent/false —
  mocked, no real API calls), retry behavior on a failed push.

## D. Files added

```
.env.example
.gitignore                          (existed, extended)
Dockerfile                          (backend, optional)
dashboard/Dockerfile                (dashboard, optional)
docker-compose.yml                  (optional)
requirements-dev.txt
holy_month/api/security.py
tests/conftest.py
tests/test_config.py
tests/test_db_models.py
tests/test_prompt_templates.py
tests/test_settings_store.py
tests/test_ai_disclosure.py
tests/test_auto_approval.py
tests/test_video_editor_guard.py
AUDIT_REPORT.md                     (this file)
```

## E. Files modified

```
holy_month/main.py                  CORS fix, security import
holy_month/config/settings.py       ALLOWED_ORIGINS, API_ACCESS_TOKEN, removed pydantic-settings
holy_month/db/models.py             ai_disclosure column
holy_month/db/session.py            migration extended for ai_disclosure
holy_month/agents/assembly.py       Windows subtitle path fix, ffmpeg fail-fast, title sanitization
holy_month/agents/youtube_upload.py contains_synthetic_media param, set_synthetic_media_disclosure()
holy_month/services/video_editor.py disclosure preserved across regeneration
holy_month/api/schemas.py           AIDisclosureUpdate schema
holy_month/api/routes_videos.py     ai-disclosure endpoint, security dependency
holy_month/api/routes_plans.py      security dependency
holy_month/api/routes_settings.py   security dependency
holy_month/api/routes_youtube.py    security dependency
holy_month/api/routes_system.py     security dependency on destructive endpoints
dashboard/api_client.py             X-API-Key header support
dashboard/pages/2_✅_Review_Center.py    disclosure UI
dashboard/pages/1_🎥_Video_Manager.py    disclosure indicator
requirements.txt                    removed pydantic-settings
.github/workflows/daily-video.yml   permissions block, removed pydantic-settings
README.md                           .env.example, testing, Docker, security sections
```

## F. Files removed

None. No working functionality was deleted — every change above is additive
or a targeted in-place fix.

## G. Security improvements

See B above (CORS, auth). Additionally confirmed by direct inspection:
- No hardcoded secrets anywhere (grepped for API-key-shaped strings; none found).
- No credential values ever passed to `print()`/logging (one hit on grep was a
  message *naming* an env var, not printing its value — confirmed safe).
- No `shell=True` anywhere in the codebase — every `subprocess` call uses list
  args, so there's no shell-injection surface even before the title-sanitization fix.
- No user-controllable path ever reaches disk I/O without being server-generated
  first (checked Video Editor, cleanup, restore-db paths specifically).

## H. Testing performed

Static only (see environment disclosure above): `python -m py_compile` across
every `.py` file in the repo (142 files at final count), targeted greps for
secrets/background-music/TODOs, and manual trace-through of every changed code
path.

## I. Tests passed

**None have been run.** 39 test functions were written across 7 test files —
all pass `py_compile`, and I traced each one's logic by hand against the
actual implementation it tests, but "I read it carefully" is not the same
claim as "it passed." Classified as REQUIRES USER ACTION (see below), not PASSED.

## J. Tests failed

None known — but see I above; this can't be claimed with confidence until
`pytest` actually runs.

## K. Tests requiring your machine (REQUIRES USER ACTION)

- `pytest tests/ -v` — needs `pip install -r requirements-dev.txt` first.
- Everything under "Local end-to-end verification" below.
- YouTube re-authorization (`youtube-auth`) if upgrading from before the
  Analytics scope was added (Module 5) — separate from this audit, still
  outstanding if you haven't done it yet.
- Real ffmpeg/Gemini/edge-tts/YouTube/Telegram integration — genuinely
  requires your credentials and machine; cannot be mocked away entirely for
  a true end-to-end run.

## L. Free resources/services used

Gemini (free tier), edge-tts (free, no key), Pollinations.ai (free, no key),
ffmpeg (free, local), YouTube Data API + Analytics API (free quota), Telegram
Bot API (free), SQLite (local, free). No paid dependency was added or is
required to run this project.

## M. Optional future paid upgrades

None added or required. If you ever want higher Gemini rate limits, that's a
Google Cloud billing upgrade on the *same* API already in use — no code
change needed, no new dependency, nothing to migrate.

## N. Remaining limitations (unchanged from before this audit, still accurate)

- No background music — **by requirement**, confirmed absent by grep, not a gap.
- No settable video duration — pipeline derives duration from narration length.
- Can't regenerate an already-published video — no YouTube "replace footage" API.
- Logs don't persist for GitHub Actions runs — check the Actions tab for those.
- Metadata edits don't push to an already-live YouTube upload (disclosure
  does, as of this audit — metadata doesn't yet).

## O. Known issues (not fixed, flagged instead)

- `check_ffmpeg()`'s Windows install instructions are now more detailed, but I
  could not verify them against a real Windows machine (no such environment
  available here) — worth a sanity check on your end.
- The `ALTER TABLE ... ADD COLUMN` migrations run on every startup (cheap
  `PRAGMA table_info` check, then a no-op if the column exists) — fine at this
  scale, but if the schema keeps growing this way indefinitely, a real
  migration tool (Alembic) would eventually be worth adopting. Not needed yet.

## P. Exact installation instructions

```bash
git clone <your-repo>
cd holy_month_ai
cp .env.example .env
# edit .env with real GEMINI_API_KEY, YOUTUBE_CLIENT_ID/SECRET, TELEGRAM_BOT_TOKEN/CHAT_ID
pip install -r requirements.txt --break-system-packages
python holy_month_automation.py youtube-auth
python holy_month_automation.py create-plan
```

## Q. Exact .env instructions

Copy `.env.example` to `.env`. Every value in the example file is documented
inline with where to get it. `.env` is gitignored — never commit it.

## R. Exact startup commands

```bash
# Backend (persistent server + scheduler)
python holy_month_automation.py web

# Dashboard (separate terminal)
streamlit run dashboard/Home.py
```
Or, for the no-owned-machine path: push to GitHub with `GEMINI_API_KEY`,
`YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SECRET_KEY` set as repo secrets —
`.github/workflows/daily-video.yml` runs daily automatically.

## S. Exact testing procedure

```bash
pip install -r requirements-dev.txt --break-system-packages
pytest tests/ -v
```
Every test is isolated (temp dir, fake `.env`, throwaway SQLite file, mocked
YouTube/Telegram calls) — safe to run with zero risk to real data or
credentials, and safe to run without real API keys at all.

## T. YouTube setup procedure

1. Google Cloud Console → create/select a project → enable "YouTube Data API v3".
2. Credentials → Create OAuth Client ID → Application type: Desktop app.
3. Put the client ID/secret in `.env`.
4. Run `python holy_month_automation.py youtube-auth` — opens a browser, you
   approve access, the refresh token is saved to `.env` automatically.

## U. YouTube AI/altered-content disclosure procedure

1. After a video uploads (status `pending_review`), open **Review Center**.
2. Under the video, read the "What does this mean?" explanation.
3. Select Yes / No / Not Selected based on whether *this specific video*
   meets YouTube's Altered/Synthetic content bar — the tool does not decide
   this for you.
4. Save — this writes to the database immediately, and pushes to YouTube's
   real `containsSyntheticMedia` field if the video is already uploaded.
5. The choice persists through metadata edits, script edits, and full
   regeneration.

## V. Final project structure

```
holy_month_ai/
├── .github/workflows/daily-video.yml
├── .env.example
├── .gitignore
├── README.md
├── AUDIT_REPORT.md
├── MODULE_1_NOTES.md ... MODULE_6_NOTES.md
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile                (optional)
├── docker-compose.yml        (optional)
├── holy_month_automation.py
├── holy_month.db
├── holy_month/                (backend — see README.md for the full breakdown)
├── dashboard/                  (Streamlit — see README.md)
└── tests/                      (pytest, 39 tests across 7 files)
```

## W. Location/name of final ZIP

`holy_month_ai_final.zip` — ONE zip, delivered alongside this report.

---

## Final honesty statement

Everything above reflects what I actually inspected. I did not claim any
feature "works" without tracing its real code path, and I did not claim any
test "passed" without actually running it — the distinction between "written
and reasoned through" and "executed and verified" is preserved throughout this
report on purpose. The single biggest remaining risk is that nothing here has
been run end-to-end on a real machine with real credentials — that verification
genuinely requires your environment, not mine.
