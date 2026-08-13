import asyncio
import os
import subprocess
import sys

# NEW (Module 6): set up log-file capture before anything else imports
# (Config's module-level install_requirements() call included) — this
# is the only way any of that early output ends up in logs/holy_month.log
# instead of just the terminal.
from holy_month.logging_setup import setup_logging
setup_logging()

import uvicorn

from holy_month.config import Config
from holy_month.db import SessionLocal, MonthlyPlan
from holy_month.agents import PlannerAgent, run_youtube_oauth_setup
from holy_month.services import HolyMonthOrchestrator
from holy_month.services.production import produce_single_video, find_due_plan
from holy_month.services.auto_approval import run_auto_approval_sweep
from holy_month.services.youtube_stats import sync_video_stats

# ============================================================
# ONE-SHOT CLI MODES (for GitHub Actions — no server, no owned machine)
# ============================================================
#
# The 'web' mode needs a machine that stays on 24/7 (a scheduler loop).
# If you don't own one, the free alternative is GitHub Actions: it runs
# this script ONCE PER DAY on a schedule, on GitHub's own free servers,
# then shuts down until tomorrow. Nothing needs to stay running on your
# end. Two modes support that:
#   - create-plan   : run ONCE (from any computer) to set up the month
#   - produce-today : what the GitHub Actions workflow calls daily


def _create_plan_from_env_or_prompt():
    """Reads plan details from environment variables if present (so this
    can run non-interactively in a workflow too), otherwise prompts."""
    theme = os.getenv("PLAN_THEME") or input("Theme (e.g. ramadan): ").strip()
    holy_month = os.getenv("PLAN_HOLY_MONTH") or input("Holy month (e.g. Ramadan): ").strip()
    audience = os.getenv("PLAN_AUDIENCE") or input("Target audience: ").strip()
    language = os.getenv("PLAN_LANGUAGE") or input("Language code [en]: ").strip() or "en"
    total = int(os.getenv("PLAN_TOTAL_VIDEOS") or input("Total videos [30]: ").strip() or "30")
    return theme, holy_month, audience, language, total


async def _create_plan_cli():
    theme, holy_month, audience, language, total = _create_plan_from_env_or_prompt()
    print(f"\n📝 Generating {total} video ideas via Gemini for '{theme}'...")
    planner = PlannerAgent()
    ideas = await asyncio.to_thread(planner.generate_ideas, theme, holy_month, audience, language, total)

    db = SessionLocal()
    try:
        plan = MonthlyPlan(theme=theme, holy_month=holy_month, target_audience=audience,
                           language=language, total_videos=total, ideas_json=ideas)
        db.add(plan)
        db.commit()
        db.refresh(plan)
        print(f"\n✅ Plan created (id={plan.id}) with {len(ideas)} ideas planned out.")
        print("   Commit the updated holy_month.db so GitHub Actions can see this plan tomorrow:")
        print("   git add holy_month.db && git commit -m 'add monthly plan' && git push")
    finally:
        db.close()


async def _produce_today_cli():
    """Called once per day by the GitHub Actions workflow. Finds the
    first active, non-paused plan that hasn't produced a video yet
    today, makes exactly one, then exits. Also sweeps for any
    pending_review video that has passed AUTO_APPROVE_AFTER_HOURS and
    publishes it — this is the ONLY place that sweep runs in the
    GitHub Actions deployment, since there's no persistent scheduler
    loop to do it continuously, so it must happen on every wake-up.
    Safe to call on a fixed daily schedule indefinitely."""
    due = find_due_plan()

    if not due:
        print("ℹ️  No plan is due for a video today (already produced today's video, "
              "no active plan, or all plans complete).")
    else:
        plan_id, day = due
        print(f"🎬 Producing plan {plan_id}, day {day}...")
        await produce_single_video(plan_id, day)
        print("✅ Video production done.")

    print("⏰ Checking for videos overdue for auto-approval...")
    auto_published = await asyncio.to_thread(run_auto_approval_sweep)
    if auto_published:
        print(f"✅ Auto-approved {len(auto_published)} video(s): {auto_published}")
    else:
        print("ℹ️  Nothing was overdue for auto-approval.")

    print("📊 Syncing YouTube stats (views/likes/comments)...")
    stats_result = await asyncio.to_thread(sync_video_stats)
    if stats_result.get("ok"):
        print(f"✅ Synced stats for {stats_result.get('updated', 0)} video(s).")
    else:
        # Best-effort: a stats sync failure (e.g. not yet reauthorized for
        # the analytics scope, or a transient API error) shouldn't fail
        # the whole daily workflow run.
        print(f"⚠️  Stats sync skipped: {stats_result.get('error')}")


# ============================================================
# 'web' MODE — persistent server for machines that stay on
# ============================================================

def run_web_server():
    from holy_month.main import app  # imported here so `main.py`'s
                                      # scheduler startup only fires
                                      # for this mode, not every CLI call

    print("\n" + "=" * 60)
    print("🕌 HOLY MONTH AI - YouTube Automation (fixed, $0/month)")
    print("=" * 60)

    if not Config.check_keys():
        print("\n❌ Please finish setup and restart.")
        return

    print("\n✅ Configuration OK! Starting system...")
    print(f"📁 Output directory: {Config.OUTPUT_DIR}")

    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("✅ FFmpeg found!")
    except Exception:
        print("⚠️  FFmpeg not found — install it before producing videos.")

    print(f"\n🚀 Dashboard: http://localhost:8000")
    print(f"⏰ Videos publish 1/day at {Config.PUBLISH_HOUR}:00 (server time) once a plan exists.")
    print(f"👀 Human review: {'ON — approve via POST /api/v1/videos/{id}/approve' if Config.REQUIRE_HUMAN_REVIEW else 'OFF — auto-public'}")
    if Config.REQUIRE_HUMAN_REVIEW and Config.AUTO_APPROVE_AFTER_HOURS > 0:
        print(f"⏰ Un-reviewed videos auto-approve after {Config.AUTO_APPROVE_AFTER_HOURS:g}h.")
    print("\nCreate a monthly plan:")
    print("  curl -X POST http://localhost:8000/api/v1/monthly-plan \\")
    print("    -H 'Content-Type: application/json' \\")
    print("    -d '{\"theme\":\"ramadan\",\"holy_month\":\"Ramadan\",\"target_audience\":\"young adults\","
          "\"preferred_language\":\"en\",\"total_videos\":30}'")
    print("\n" + "=" * 60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


# ============================================================
# MAIN
# ============================================================

def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "youtube-auth":
            run_youtube_oauth_setup()
        elif sys.argv[1] == "web":
            run_web_server()
        elif sys.argv[1] == "create-plan":
            asyncio.run(_create_plan_cli())
        elif sys.argv[1] == "produce-today":
            asyncio.run(_produce_today_cli())
        elif sys.argv[1] == "test":
            async def _test():
                orchestrator = HolyMonthOrchestrator()
                result = await orchestrator.produce_video("ramadan", 1, "Introduction to Ramadan", "en")
                print(f"Test result: {result}")
            asyncio.run(_test())
        else:
            print("Usage:")
            print("  python holy_month_automation.py youtube-auth   - one-time YouTube OAuth setup")
            print("  python holy_month_automation.py create-plan    - one-time: set up this month's plan")
            print("  python holy_month_automation.py produce-today  - produce today's video + run auto-approval sweep, then exit")
            print("                                                   (this is what GitHub Actions calls daily)")
            print("  python holy_month_automation.py web            - run as a persistent server (needs a machine that stays on)")
            print("  python holy_month_automation.py test           - produce one test video immediately")
    else:
        run_web_server()


if __name__ == "__main__":
    main()
