# Module 3 — Monthly Planner

## Backend changes (new, additive — nothing existing removed)

`holy_month/api/schemas.py` — two new request models: `MonthlyPlanUpdate`, `MonthlyPlanDuplicate`.

`holy_month/api/routes_plans.py` — four new endpoints:

| Endpoint | What it does |
|---|---|
| `PUT /api/v1/plans/{id}` | Edit audience / language / total_videos. Theme & holy_month are **not** editable here — every stored idea was generated against the original theme, so changing it without regenerating would leave old day-numbers describing the wrong topic. Shrinking `total_videos` below what's already been produced is rejected. |
| `DELETE /api/v1/plans/{id}` | Deletes the plan row. Already-produced videos are **kept**, with `plan_id` set to NULL — deleting a plan never deletes videos or unpublishes anything on YouTube. |
| `POST /api/v1/plans/{id}/duplicate` | New plan, same theme/audience/language/count. Defaults to a **fresh** Gemini-generated idea set (not a literal copy) — `reuse_ideas: true` in the body copies verbatim if you specifically want that. |
| `POST /api/v1/plans/{id}/regenerate-ideas` | Regenerates ideas only for days **not yet produced** — already-published days keep their original stored idea untouched, so nothing already public ends up mismatched against a new topic list. |

## Dashboard changes

- `db_reader.py`: added `fetch_plan_videos()` for the calendar view, and fixed a latent bug — `tags`/`hashtags`/`ideas_json` etc. are JSON columns, but plain `sqlite3` (unlike the SQLAlchemy ORM the backend uses) doesn't auto-parse them, so they were rendering as raw `'["a","b"]'` strings in Video Manager. Now parsed properly everywhere.
- `api_client.py`: `update_plan`, `delete_plan`, `duplicate_plan`, `regenerate_ideas` — same fail-soft pattern as the existing functions.
- `pages/3_🗓️_Monthly_Planner.py`: full page — **Existing Plans** tab (progress bar, estimated completion date, pause/resume, produce-next, regenerate, duplicate, edit-in-place, delete-with-confirmation, and a calendar grid showing every day's idea + video status) and **Create New Plan** tab (theme/audience/language/duration/count form, with a generated-ideas preview after submit).

## Things worth knowing before you rely on this

- **Delete has a confirmation step** (click once to arm it, again to confirm) but there's no undo — the plan row is gone, though produced videos survive.
- **Regenerate-ideas and Create-plan both call Gemini** for up to 30 ideas, so the dashboard timeout for those calls is set to 120s instead of the usual 30s. On a slow connection or a big `total_videos`, it can still take a moment — the spinner will sit there; that's expected, not a hang.
- Every planner action needs the **live backend** (`python holy_month_automation.py web`) — none of this works in pure read-only mode, since creating/editing/deleting all write to the DB or call Gemini.

## Verify locally

```bash
python holy_month_automation.py web   # in one terminal
streamlit run dashboard/Home.py       # in another
```
Then open the Monthly Planner page, create a small test plan (e.g. `total_videos=2`) before trusting it with a real 30-day plan.
