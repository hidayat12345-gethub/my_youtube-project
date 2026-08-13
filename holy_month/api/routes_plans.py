import asyncio

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends

from holy_month.config import Config
from holy_month.db import SessionLocal, MonthlyPlan, Video
from holy_month.agents import PlannerAgent
from holy_month.services.production import produce_single_video
from .schemas import MonthlyPlanCreate, MonthlyPlanUpdate, MonthlyPlanDuplicate
from .security import verify_api_key

# FIX (audit): router-level dependency — every endpoint here (including
# reads) requires X-API-Key when Config.API_ACCESS_TOKEN is set; no-op
# in local/dev mode (unset token). See security.py.
router = APIRouter(prefix="/api/v1", tags=["plans"], dependencies=[Depends(verify_api_key)])


@router.post("/monthly-plan")
async def create_monthly_plan(plan: MonthlyPlanCreate):
    """Only creates the plan record (production happens one video per
    day via the background scheduler — see daily_scheduler_loop).
    Generates the full ideas list ONCE, right now, and stores it —
    instead of each day separately asking Gemini for "the N ideas" and
    picking one out, which was non-deterministic and could drift/
    duplicate across days."""
    planner = PlannerAgent()
    ideas = await asyncio.to_thread(
        planner.generate_ideas, plan.theme, plan.holy_month, plan.target_audience,
        plan.preferred_language, plan.total_videos,
    )

    db = SessionLocal()
    try:
        monthly_plan = MonthlyPlan(
            theme=plan.theme, holy_month=plan.holy_month, target_audience=plan.target_audience,
            language=plan.preferred_language, total_videos=plan.total_videos, ideas_json=ideas,
        )
        db.add(monthly_plan)
        db.commit()
        db.refresh(monthly_plan)
        plan_id = monthly_plan.id
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

    return {"status": "success", "plan_id": plan_id, "idea_count": len(ideas),
            "message": (f"Plan created with {len(ideas)} video ideas planned out. One video will be "
                        f"produced per day at {Config.PUBLISH_HOUR}:00 automatically, "
                        f"or POST /api/v1/produce-next/{plan_id} to produce the first one now.")}


@router.get("/plans")
async def list_plans():
    """NEW — the dashboard's Monthly Planner page needs to list every
    plan, not just look one up by id."""
    db = SessionLocal()
    try:
        plans = db.query(MonthlyPlan).order_by(MonthlyPlan.created_at.desc()).all()
        return [{
            "id": p.id, "theme": p.theme, "holy_month": p.holy_month,
            "target_audience": p.target_audience, "language": p.language,
            "total_videos": p.total_videos, "current_day": p.current_day,
            "is_active": p.is_active, "is_paused": p.is_paused,
            "start_date": p.start_date.isoformat() if p.start_date else None,
            "last_produced_date": p.last_produced_date.isoformat() if p.last_produced_date else None,
        } for p in plans]
    finally:
        db.close()


@router.get("/plans/{plan_id}")
async def get_plan(plan_id: int):
    """NEW — plan detail, including the stored per-day ideas list, for
    the Monthly Planner's calendar/progress view."""
    db = SessionLocal()
    try:
        plan = db.query(MonthlyPlan).filter(MonthlyPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(404, "Plan not found")
        return {
            "id": plan.id, "theme": plan.theme, "holy_month": plan.holy_month,
            "target_audience": plan.target_audience, "language": plan.language,
            "total_videos": plan.total_videos, "current_day": plan.current_day,
            "is_active": plan.is_active, "is_paused": plan.is_paused,
            "ideas": plan.ideas_json or [],
            "start_date": plan.start_date.isoformat() if plan.start_date else None,
            "last_produced_date": plan.last_produced_date.isoformat() if plan.last_produced_date else None,
        }
    finally:
        db.close()


@router.post("/produce-next/{plan_id}")
async def produce_next(plan_id: int, background_tasks: BackgroundTasks):
    """Manually trigger production of the next video in a plan (for
    testing, or to produce today's video immediately instead of
    waiting for the scheduled hour)."""
    db = SessionLocal()
    try:
        plan = db.query(MonthlyPlan).filter(MonthlyPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(404, "Plan not found")
        if plan.current_day >= plan.total_videos:
            return {"status": "complete", "message": "All videos in this plan have been produced."}
        if plan.is_paused:
            raise HTTPException(400, "Plan is paused. Resume it first: POST /api/v1/plans/{id}/resume")
        next_day = plan.current_day + 1
    finally:
        db.close()

    background_tasks.add_task(produce_single_video, plan_id, next_day)
    return {"status": "queued", "plan_id": plan_id, "day": next_day}


@router.post("/plans/{plan_id}/pause")
async def pause_plan(plan_id: int):
    db = SessionLocal()
    try:
        plan = db.query(MonthlyPlan).filter(MonthlyPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(404, "Plan not found")
        plan.is_paused = True
        db.commit()
    finally:
        db.close()
    return {"plan_id": plan_id, "is_paused": True}


@router.post("/plans/{plan_id}/resume")
async def resume_plan(plan_id: int):
    db = SessionLocal()
    try:
        plan = db.query(MonthlyPlan).filter(MonthlyPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(404, "Plan not found")
        plan.is_paused = False
        db.commit()
    finally:
        db.close()
    return {"plan_id": plan_id, "is_paused": False}


# ============================================================
# NEW (Module 3) — edit / delete / duplicate / regenerate
# ============================================================

@router.put("/plans/{plan_id}")
async def update_plan(plan_id: int, update: MonthlyPlanUpdate):
    """Edits audience/language/total_videos only. theme/holy_month are
    intentionally NOT editable here — every stored idea in ideas_json
    was generated against the original theme, so changing it without
    regenerating would silently leave "Day 12" describing the wrong
    theme. Use regenerate-ideas (or duplicate) for that instead.

    Shrinking total_videos below current_day is rejected (would orphan
    already-produced videos' day numbering against a plan that claims
    to be already finished). Growing it is fine — it just means more
    days get produced, and any newly-added days beyond what ideas_json
    already covers fall back to produce_single_video's on-the-fly
    Gemini call (see services/production.py), same as an old plan
    missing a day's stored idea."""
    db = SessionLocal()
    try:
        plan = db.query(MonthlyPlan).filter(MonthlyPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(404, "Plan not found")

        if update.total_videos is not None and update.total_videos < plan.current_day:
            raise HTTPException(
                400, f"Can't set total_videos to {update.total_videos} — "
                     f"{plan.current_day} videos have already been produced.")

        if update.target_audience is not None:
            plan.target_audience = update.target_audience
        if update.preferred_language is not None:
            plan.language = update.preferred_language
        if update.total_videos is not None:
            plan.total_videos = update.total_videos

        db.commit()
        db.refresh(plan)
        return {"status": "success", "plan_id": plan.id, "target_audience": plan.target_audience,
                "language": plan.language, "total_videos": plan.total_videos}
    finally:
        db.close()


@router.delete("/plans/{plan_id}")
async def delete_plan(plan_id: int):
    """Deletes the plan record. Any videos already produced under it
    are kept (not deleted) — their plan_id is set to NULL so they don't
    silently disappear from the Video Manager / your YouTube channel
    just because the plan row is gone."""
    db = SessionLocal()
    try:
        plan = db.query(MonthlyPlan).filter(MonthlyPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(404, "Plan not found")

        db.query(Video).filter(Video.plan_id == plan_id).update({"plan_id": None})
        db.delete(plan)
        db.commit()
        return {"status": "deleted", "plan_id": plan_id}
    finally:
        db.close()


@router.post("/plans/{plan_id}/duplicate")
async def duplicate_plan(plan_id: int, options: MonthlyPlanDuplicate):
    """Creates a brand-new plan with the same theme/audience/language/
    total_videos. Defaults to generating a FRESH set of ideas (not
    literally copying ideas_json) — duplicating is normally "do another
    month like this one", and re-uploading the exact same 30 video
    ideas would just re-produce near-duplicate content. Set
    reuse_ideas=true if you specifically want an identical copy (e.g.
    to re-run a month you deleted by mistake)."""
    db = SessionLocal()
    try:
        source = db.query(MonthlyPlan).filter(MonthlyPlan.id == plan_id).first()
        if not source:
            raise HTTPException(404, "Plan not found")
        theme, holy_month, target_audience, language, total_videos = (
            source.theme, source.holy_month, source.target_audience, source.language, source.total_videos)
        source_ideas = source.ideas_json
    finally:
        db.close()

    if options.reuse_ideas and source_ideas:
        ideas = source_ideas
    else:
        planner = PlannerAgent()
        ideas = await asyncio.to_thread(
            planner.generate_ideas, theme, holy_month, target_audience, language, total_videos)

    db = SessionLocal()
    try:
        new_plan = MonthlyPlan(theme=theme, holy_month=holy_month, target_audience=target_audience,
                               language=language, total_videos=total_videos, ideas_json=ideas)
        db.add(new_plan)
        db.commit()
        db.refresh(new_plan)
        return {"status": "success", "plan_id": new_plan.id, "idea_count": len(ideas),
                "reused_ideas": bool(options.reuse_ideas and source_ideas)}
    finally:
        db.close()


@router.post("/plans/{plan_id}/regenerate-ideas")
async def regenerate_ideas(plan_id: int):
    """Regenerates ideas for days that haven't been produced YET —
    days <= current_day keep their original stored idea untouched, so
    already-published videos never end up mismatched against a
    regenerated topic list. Use this when the AI-suggested topics for
    the rest of the month aren't landing and you want a fresh batch."""
    db = SessionLocal()
    try:
        plan = db.query(MonthlyPlan).filter(MonthlyPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(404, "Plan not found")
        theme, holy_month, target_audience, language, total_videos = (
            plan.theme, plan.holy_month, plan.target_audience, plan.language, plan.total_videos)
        current_day, old_ideas = plan.current_day, (plan.ideas_json or [])
    finally:
        db.close()

    planner = PlannerAgent()
    fresh_ideas = await asyncio.to_thread(
        planner.generate_ideas, theme, holy_month, target_audience, language, total_videos)

    preserved = [i for i in old_ideas if i.get("day", 0) <= current_day]
    preserved_days = {i.get("day") for i in preserved}
    merged = preserved + [i for i in fresh_ideas if i.get("day") not in preserved_days]
    merged.sort(key=lambda i: i.get("day", 0))

    db = SessionLocal()
    try:
        plan = db.query(MonthlyPlan).filter(MonthlyPlan.id == plan_id).first()
        plan.ideas_json = merged
        db.commit()
        return {"status": "success", "plan_id": plan_id,
                "regenerated_days": total_videos - len(preserved), "preserved_days": len(preserved)}
    finally:
        db.close()
