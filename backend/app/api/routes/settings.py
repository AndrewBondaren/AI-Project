from typing import Any
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.appSettings import app_settings
from app.application.llm.language import Language
from app.application.engine.repair.repairMode import RepairMode

router = APIRouter()


class SettingsUpdate(BaseModel):
    qwen_base_url:      str  | None = None
    qwen_api_key:       str  | None = None
    openai_base_url:    str  | None = None
    openai_api_key:     str  | None = None
    anthropic_base_url: str  | None = None
    anthropic_api_key:  str  | None = None
    llm_streaming:      bool | None = None
    max_tokens:         int  | None = None
    language:           Language | None = None
    repair_iterations:  int  | None = None
    max_passes:         int  | None = None
    repair_mode:        RepairMode | None = None


@router.get("/settings")
def get_settings() -> dict[str, Any]:
    return {
        "qwen_base_url":      app_settings.qwen_base_url,
        "openai_base_url":    app_settings.openai_base_url,
        "anthropic_base_url": app_settings.anthropic_base_url,
        "llm_streaming":      app_settings.llm_streaming,
        "max_tokens":         app_settings.max_tokens,
        "language":           app_settings.language,
        "repair_iterations":  app_settings.repair_iterations,
        "max_passes":         app_settings.max_passes,
        "repair_mode":        app_settings.repair_mode,
    }


@router.put("/settings")
def update_settings(data: SettingsUpdate) -> dict[str, Any]:
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    app_settings.update(**updates)
    return {"ok": True, "updated": list(updates.keys())}
