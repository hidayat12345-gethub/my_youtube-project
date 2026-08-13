from fastapi import APIRouter, HTTPException, Depends

from holy_month.services.youtube_stats import (
    sync_video_stats, fetch_channel_summary, fetch_channel_analytics, fetch_recent_comments,
)
from .security import verify_api_key

# FIX (audit): see routes_plans.py — same router-level auth pattern.
router = APIRouter(prefix="/api/v1/youtube", tags=["youtube"], dependencies=[Depends(verify_api_key)])


@router.post("/sync-stats")
async def sync_stats():
    """Pulls current view/like/comment counts for every uploaded video
    from the YouTube Data API and updates the DB. Also runs
    automatically once/day from the scheduler and from produce-today
    (see services/scheduler.py and cli.py) — this endpoint is for an
    on-demand refresh from the dashboard."""
    result = sync_video_stats()
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    return result


@router.get("/channel-summary")
async def channel_summary():
    result = fetch_channel_summary()
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    return result


@router.get("/analytics")
async def analytics(days: int = 28):
    result = fetch_channel_analytics(days=days)
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    return result


@router.get("/comments")
async def comments(max_results: int = 10):
    result = fetch_recent_comments(max_results=max_results)
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    return result
