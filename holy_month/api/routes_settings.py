from fastapi import APIRouter, HTTPException, Depends

from holy_month.services import settings_store, prompt_templates
from .schemas import AISettingsUpdate, PromptTemplateUpdate
from .security import verify_api_key

# FIX (audit): see routes_plans.py — same router-level auth pattern.
# Especially relevant here — prompt templates + AI settings shape the
# actual content generated, worth protecting even the reads.
router = APIRouter(prefix="/api/v1/settings", tags=["settings"], dependencies=[Depends(verify_api_key)])


@router.get("")
async def get_settings():
    return settings_store.get_all_settings()


@router.put("")
async def update_settings(update: AISettingsUpdate):
    updates = update.model_dump(exclude_unset=True)
    return settings_store.update_settings(updates)


@router.post("/reset")
async def reset_settings():
    return settings_store.reset_settings()


@router.get("/prompts")
async def get_prompts():
    return prompt_templates.get_all_templates()


@router.put("/prompts/{key}")
async def update_prompt(key: str, update: PromptTemplateUpdate):
    try:
        prompt_templates.set_template(key, update.text)
    except KeyError as e:
        raise HTTPException(404, str(e))
    return {"status": "success", "key": key}


@router.post("/prompts/{key}/reset")
async def reset_prompt(key: str):
    try:
        default_text = prompt_templates.reset_template(key)
    except KeyError as e:
        raise HTTPException(404, str(e))
    return {"status": "success", "key": key, "text": default_text}
