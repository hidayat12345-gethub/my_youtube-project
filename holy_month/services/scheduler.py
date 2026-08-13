import asyncio
import datetime as _dt

from holy_month.config import Config
from .production import produce_single_video, find_all_due_plans
from .auto_approval import run_auto_approval_sweep
from .youtube_stats import sync_video_stats

_last_stats_sync_date = None


async def daily_scheduler_loop():
    """Replaces the old 'produce all 30 videos 5 seconds apart'
    approach. Checks periodically whether it's past PUBLISH_HOUR and an
    active, non-paused plan hasn't produced today's video yet — if so,
    produces exactly ONE video per due plan, then waits for the next
    check. Also sweeps for any pending_review video that has passed
    AUTO_APPROVE_AFTER_HOURS and publishes it automatically, every
    cycle (not just at PUBLISH_HOUR), so approval delay never depends
    on the production check timing. Also syncs YouTube view/like/
    comment stats once per day (not every cycle — no need to burn API
    quota checking stats every 15 minutes)."""
    global _last_stats_sync_date
    print(f"⏰ Daily scheduler started (checks every "
          f"{Config.SCHEDULER_CHECK_INTERVAL_MINUTES} min, publish hour={Config.PUBLISH_HOUR}:00, "
          f"auto-approve after={Config.AUTO_APPROVE_AFTER_HOURS:g}h)")
    while True:
        try:
            now = _dt.datetime.now()
            if now.hour >= Config.PUBLISH_HOUR:
                for plan_id, day in find_all_due_plans():
                    print(f"⏰ Scheduler: producing plan {plan_id} day {day}")
                    await produce_single_video(plan_id, day)

                if _last_stats_sync_date != now.date():
                    result = await asyncio.to_thread(sync_video_stats)
                    if result.get("ok"):
                        print(f"📊 Synced YouTube stats for {result.get('updated', 0)} video(s).")
                    else:
                        print(f"⚠️  YouTube stats sync skipped: {result.get('error')}")
                    _last_stats_sync_date = now.date()

            # NEW: runs every cycle regardless of PUBLISH_HOUR, so a
            # video approaching its 20h window isn't left waiting for
            # the next production check to fire.
            await asyncio.to_thread(run_auto_approval_sweep)

        except Exception as e:
            print(f"⚠️  Scheduler loop error (will retry next cycle): {e}")

        await asyncio.sleep(Config.SCHEDULER_CHECK_INTERVAL_MINUTES * 60)
