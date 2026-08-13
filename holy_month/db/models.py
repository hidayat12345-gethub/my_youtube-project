"""SQLAlchemy models - unchanged schema from the original single file.
No columns were added or removed; the only behavioral change elsewhere
in the app is that `uploaded_at` is now actually populated (it existed
as a column before but was never written to), and `status` can now
additionally take the value 'auto_published' alongside the original
pending / producing / pending_review / published / failed / saved_locally.
"""

from datetime import datetime

from sqlalchemy import (Column, Integer, String, Text, DateTime,
                         Float, Boolean, JSON, ForeignKey)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class MonthlyPlan(Base):
    __tablename__ = 'monthly_plans'

    id = Column(Integer, primary_key=True)
    theme = Column(String(100))
    holy_month = Column(String(100))
    target_audience = Column(String(255))
    language = Column(String(10), default='en')
    total_videos = Column(Integer, default=30)
    current_day = Column(Integer, default=0)          # how many videos produced so far
    is_active = Column(Boolean, default=True)
    is_paused = Column(Boolean, default=False)
    start_date = Column(DateTime, default=datetime.now)
    # Without this, the scheduler has no way to know "have we already
    # produced today's video?" and would either double-produce or
    # never produce, depending on how it's polled.
    last_produced_date = Column(DateTime, nullable=True)
    # Ideas are generated ONCE at plan creation and stored here (not
    # regenerated daily), so "Day 5" is a fixed, deterministic topic
    # rather than something that could drift/duplicate across days.
    ideas_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class Video(Base):
    __tablename__ = 'videos'

    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey('monthly_plans.id'), nullable=True)
    day_index = Column(Integer, nullable=True)

    title = Column(String(500))
    description = Column(Text)
    script = Column(Text)
    # pending -> producing -> pending_review -> published -> failed
    # (also: 'saved_locally' if upload failed/no auth, 'auto_published'
    # if the 20h auto-approval sweep published it instead of a human)
    status = Column(String(50), default='pending')
    publish_date = Column(DateTime)

    research = Column(JSON)
    scenes = Column(JSON)

    voice_audio_path = Column(String(500))
    video_path = Column(String(500))
    thumbnail_path = Column(String(500))

    youtube_video_id = Column(String(100))
    youtube_url = Column(String(500))

    tags = Column(JSON)
    hashtags = Column(JSON)

    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    ctr = Column(Float, default=0.0)
    # NEW (Module 5) — comment count from the YouTube Data API sync job.
    comments = Column(Integer, default=0)

    # NEW (audit) — separate from "AI Generated" (which is just true for
    # everything this pipeline makes). This is the human's explicit
    # publishing/compliance choice for YouTube's Altered/Synthetic
    # content disclosure (status.containsSyntheticMedia). One of:
    # 'not_selected' (default — nobody has reviewed this yet),
    # 'yes', 'no'. See holy_month/services/video_editor.py and
    # api/routes_videos.py for where this gets read/written/pushed to
    # YouTube.
    ai_disclosure = Column(String(20), default='not_selected')

    created_at = Column(DateTime, default=datetime.now)
    uploaded_at = Column(DateTime)
