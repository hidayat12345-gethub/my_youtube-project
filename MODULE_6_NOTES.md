# Module 6 — AI Settings, System Settings, Logs

## New files this creates at your repo root (add to .gitignore or commit — your call)

- `holy_month_settings.json` — generation settings (temperature, model override, thumbnail/caption styling). Created with defaults on first access; nothing changes for anyone who never opens AI Settings.
- `holy_month_prompt_templates.json` — the three editable prompts. Same deal — created with byte-for-byte the original hardcoded prompts as defaults.
- `logs/holy_month.log` — captured stdout/stderr. Grows up to ~5MB then self-truncates to the most recent half (simple home-grown rotation, no dependency added for it).
- `backups/` — only created if you use the System Settings snapshot button.

None of these files is required — every one is created lazily and defaults to exactly the pre-Module-6 behavior.

## AI Settings

**Temperature & model** (`holy_month/utils.py`): `gemini_json()` now reads `gemini_temperature`/`gemini_model` from the settings store and passes them through `google.genai.types.GenerateContentConfig`. Wrapped in a `try/except TypeError` — if your installed `google-genai` version's `generate_content()` signature doesn't match, it silently falls back to the original no-config call instead of breaking every AI call in the app.

**Prompt templates** (`holy_month/services/prompt_templates.py`): switched from Python f-strings to `string.Template` (`$placeholder` syntax) specifically because the prompts contain literal JSON examples full of `{curly braces}` — `str.format` would need every one of those escaped to `{{ }}`, which is exactly the kind of thing that quietly breaks when someone edits a prompt in a text box. `$placeholders` don't collide with `{ }` at all. Defaults are byte-for-byte identical to the original hardcoded prompts in `planner.py`/`research.py`/`script_writer.py`.

**Thumbnail & captions**: `ThumbnailAgent` and `VideoAssemblyAgent` now read text color/font size and caption font size from the settings store instead of the hardcoded gold/56px/20px. Same lazy-import pattern as everywhere else in this module (see "why so many lazy imports" below).

**Explicitly not built**: background music volume. The pipeline has zero audio-mixing capability — there's no track to set a volume for. The AI Settings page says this directly instead of shipping a control that does nothing.

## System Settings

- `/health` now also checks for `ffmpeg` on the backend's PATH via `shutil.which` — additive, doesn't change the existing response shape.
- **Output folder**: lists final files vs. temp `work_*`/`regen_*` directories with sizes. Cleanup cross-checks every temp directory against every video's `video_path`/`thumbnail_path` in the DB before removing it — important because `ThumbnailAgent` saves each thumbnail *inside* its work directory and never moves it, so a directory that looks disposable can still be something the dashboard is actively displaying.
- **Backup**: download the live DB directly, or snapshot it server-side into `backups/`.
- **Restore**: validates the uploaded file is actually a readable SQLite DB with a `videos` table before touching anything, auto-snapshots the *current* DB first (so a bad restore is itself reversible), then swaps the file in. I flagged in both the API and the UI that a server restart is recommended afterward — SQLAlchemy's connection pool already has the old file open, and swapping the file underneath a live connection isn't a fully clean hot-swap for SQLite. This isn't a limitation I could code around without adding a much heavier database layer, so I surfaced it instead of pretending it's seamless.

## Logs

The pipeline has always used `print()`, never Python's `logging` module. Rewriting ~40 call sites across every agent/service/route to `logger.info()` would be exactly the "rewrite working code" this project has avoided in every other module. Instead, `holy_month/logging_setup.py` installs a tee on `sys.stdout`/`sys.stderr` that duplicates every write to both the real console and `logs/holy_month.log` — every existing `print()` gets captured for free, zero call sites touched.

**Real limitation, stated plainly on the Logs page itself**: this doesn't help the GitHub Actions deployment. Each `produce-today` run is a fresh, throwaway runner, and `daily-video.yml` doesn't commit `logs/` back to the repo (deliberately — versioning raw logs is noisy). For that deployment, a given day's output lives in GitHub's own Actions tab, not here.

The dashboard Logs page reads the local log file directly off disk (works without a live backend, matching the pattern from every other read-only page), with search and a heuristic error/warning filter (based on the `❌`/`⚠️` emoji and "error"/"warning" text already present in the existing print statements — not real structured log levels, since nothing in the codebase sets those).

## Why so many "lazy import" comments

Several edits (`utils.py`, `thumbnail.py`, `assembly.py`, `planner.py`, `research.py`, `script_writer.py`) import from `holy_month.services` *inside* the function body instead of at the top of the file. This is deliberate, not sloppy: `holy_month.services` imports `orchestrator`, which imports `holy_month.agents`, which imports these exact files — importing `services` back at module top in any of them would be a circular import. By the time these functions actually run, every module is already fully loaded, so importing there is safe. Every instance is commented at the call site.

## Verify locally

```bash
python holy_month_automation.py web
streamlit run dashboard/Home.py
```
Open AI Settings, nudge the temperature slider and save, produce a test video and confirm it still works. Open System Settings and try the health check + output folder view. Open Logs and confirm you're seeing real output after a production run.
