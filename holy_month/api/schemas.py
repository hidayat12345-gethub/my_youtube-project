from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class MonthlyPlanCreate(BaseModel):
    theme: str = Field(..., description="Theme: ramadan, eid, hajj, etc.")
    holy_month: str = Field(..., description="Holy month name")
    target_audience: str = Field(..., description="Who is this for?")
    preferred_language: str = Field("en", description="en, ar, ur, etc.")
    video_duration: str = Field("5min", description="3min, 5min, or 10min")
    total_videos: int = Field(30, ge=1, le=31)


class MonthlyPlanUpdate(BaseModel):
    """Only fields that don't invalidate the stored ideas_json are
    editable here. Changing theme/holy_month after ideas were generated
    would leave every stored idea describing the wrong theme — that's
    what regenerate-ideas is for instead."""
    target_audience: Optional[str] = None
    preferred_language: Optional[str] = None
    total_videos: Optional[int] = Field(None, ge=1, le=31)


class MonthlyPlanDuplicate(BaseModel):
    reuse_ideas: bool = Field(
        False, description="If true, copy the same ideas_json as-is. If false "
                            "(default), generate a fresh set of ideas via Gemini.")


class VideoResponse(BaseModel):
    id: int
    title: str
    status: str
    day_index: Optional[int]
    youtube_url: Optional[str]
    created_at: datetime
    ai_disclosure: Optional[str] = "not_selected"


class VideoMetadataUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    hashtags: Optional[List[str]] = None


class VideoScriptUpdate(BaseModel):
    """Mirrors ScriptWriterAgent's output shape. Saves the edited script
    to the DB only — does not by itself regenerate voice/images/video.
    Call /regenerate afterwards to actually re-render from this script."""
    title: Optional[str] = None
    hook: Optional[str] = None
    introduction: Optional[str] = None
    body: Optional[List[str]] = None
    ending: Optional[str] = None
    call_to_action: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    hashtags: Optional[List[str]] = None
    pinned_comment: Optional[str] = None


class VideoRegenerateRequest(BaseModel):
    voice: str = Field("en", description="Voice id — one of VoiceAgent.VOICES: "
                                          "en, en-male, ar, ur.")
    language: Optional[str] = Field(None, description="Overrides the plan's language "
                                                        "for this regeneration only.")


class AISettingsUpdate(BaseModel):
    """All fields optional — only the ones provided get changed. See
    holy_month/services/settings_store.py for defaults."""
    gemini_model: Optional[str] = Field(None, description="Overrides Config.GEMINI_MODEL. "
                                                            "Leave unset to use the .env default.")
    gemini_temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    thumbnail_text_color: Optional[str] = Field(None, description="Hex color, e.g. #FFD700")
    thumbnail_font_size: Optional[int] = Field(None, ge=20, le=120)
    caption_font_size: Optional[int] = Field(None, ge=10, le=48)


class PromptTemplateUpdate(BaseModel):
    text: str


class AIDisclosureUpdate(BaseModel):
    """YouTube's Altered/Synthetic content disclosure choice — kept
    deliberately separate from any 'AI Generated' status. See
    api/routes_videos.py's set_ai_disclosure endpoint for the full
    reasoning and holy_month/agents/youtube_upload.py for the real
    YouTube Data API field this maps to (status.containsSyntheticMedia,
    added Oct 30 2024 — verified current, not invented)."""
    value: str = Field(..., description="One of: 'yes', 'no', 'not_selected'.")

    @field_validator("value")
    @classmethod
    def check_value(cls, v):
        if v not in ("yes", "no", "not_selected"):
            raise ValueError("value must be 'yes', 'no', or 'not_selected'")
        return v
