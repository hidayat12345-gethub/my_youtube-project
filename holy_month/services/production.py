import asyncio
from datetime import datetime

from holy_month.db import SessionLocal, MonthlyPlan
from holy_month.agents import PlannerAgent
from .orchestrator import HolyMonthOrchestrator


async def produce_single_video(plan_id: int, day: int):
    """Produces exactly ONE video (the given day) for the given plan.
    Reads that day's idea from the list generated ONCE at plan-creation
    time (plan.ideas_json) instead of asking Gemini to regenerate and
    re-pick from the full idea list every day, which was
    non-deterministic. Falls back to a fresh Gemini call only if the
    plan predates that fix (ideas_json is empty) or is missing that
    day's entry."""
    db = SessionLocal()
    try:
        plan = db.query(MonthlyPlan).filter(MonthlyPlan.id == plan_id).first()
        if not plan:
            print(f"⚠️  Scheduler: plan {plan_id} not found, skipping.")
            return
        theme, holy_month, target_audience, language = (
            plan.theme, plan.holy_month, plan.target_audience, plan.language)
        total_videos = plan.total_videos
        stored_ideas = plan.ideas_json or []
    finally:
        db.close()

    idea = next((i for i in stored_ideas if i.get("day") == day), None)
    if idea is None:
        print(f"⚠️  Plan {plan_id} has no stored idea for day {day} — generating one now as a fallback.")
        planner = PlannerAgent()
        ideas = await asyncio.to_thread(
            planner.generate_ideas, theme, holy_month, target_audience, language, total_videos,
        )
        idea = next((i for i in ideas if i["day"] == day), ideas[min(day - 1, len(ideas) - 1)])

    orchestrator = HolyMonthOrchestrator()
    await orchestrator.produce_video(theme=theme, day=day, title=idea["title"],
                                      language=language, plan_id=plan_id)

    db = SessionLocal()
    try:
        plan = db.query(MonthlyPlan).filter(MonthlyPlan.id == plan_id).first()
        if plan:
            plan.current_day = day
            plan.last_produced_date = datetime.now()
            db.commit()
    finally:
        db.close()


def find_due_plan() -> tuple:
    """Returns (plan_id, day) for the first active, non-paused plan that
    hasn't produced a video today and isn't finished yet — or None if
    nothing is due. Shared by the scheduler loop and the produce-today
    CLI command so both use identical "what's due" logic."""
    now = datetime.now()
    db = SessionLocal()
    try:
        plans = db.query(MonthlyPlan).filter(
            MonthlyPlan.is_active.is_(True), MonthlyPlan.is_paused.is_(False),
        ).all()
        for plan in plans:
            already_ran_today = (plan.last_produced_date is not None
                                  and plan.last_produced_date.date() == now.date())
            if not already_ran_today and plan.current_day < plan.total_videos:
                return (plan.id, plan.current_day + 1)
        return None
    finally:
        db.close()


def find_all_due_plans() -> list:
    """Like find_due_plan but returns every due plan, not just the
    first — used by the persistent 'web' scheduler loop, which can
    service more than one active plan per cycle."""
    now = datetime.now()
    db = SessionLocal()
    try:
        plans = db.query(MonthlyPlan).filter(
            MonthlyPlan.is_active.is_(True), MonthlyPlan.is_paused.is_(False),
        ).all()
        due = []
        for plan in plans:
            already_ran_today = (plan.last_produced_date is not None
                                  and plan.last_produced_date.date() == now.date())
            if not already_ran_today and plan.current_day < plan.total_videos:
                due.append((plan.id, plan.current_day + 1))
        return due
    finally:
        db.close()
