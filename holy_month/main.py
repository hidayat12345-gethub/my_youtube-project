import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# NEW (Module 6): defensive — normally already set up by cli.py's module
# top by the time this file is imported, but this covers the case of
# someone running `uvicorn holy_month.main:app` directly. Idempotent.
from holy_month.logging_setup import setup_logging
setup_logging()

from holy_month.api import routes_plans, routes_videos, routes_system, routes_youtube, routes_settings
from holy_month.services import daily_scheduler_loop
from holy_month.config import Config

app = FastAPI(
    title="Holy Month AI - YouTube Automation",
    description="AI-powered YouTube video automation system (100% free-tier services)",
    version="1.1.0",
)

# FIX (audit): was allow_origins=["*"] — accepted requests from ANY
# origin, not just this project's own dashboard. Now reads from
# Config.ALLOWED_ORIGINS (.env-configurable, defaults to localhost
# Streamlit ports only). Still no allow_credentials since nothing here
# uses cookies.
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_system.router)
app.include_router(routes_plans.router)
app.include_router(routes_videos.router)
app.include_router(routes_youtube.router)
app.include_router(routes_settings.router)


@app.on_event("startup")
async def start_scheduler():
    asyncio.create_task(daily_scheduler_loop())
