"""Normalize race template wire via POJO — tz_world_bundle WB-13."""

from __future__ import annotations

from typing import Any

from app.dataModel.races.raceTemplateOutline import RaceTemplateOutline


def normalize_race_template_body(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate + canonicalize wire (incl. legacy aliases) → dict for ``Race`` row."""
    outline = RaceTemplateOutline.model_validate(raw)
    data = outline.model_dump(mode="json")
    if not outline.template_uid or not outline.system_name or not outline.display_name:
        raise ValueError("RaceTemplateOutline identity incomplete after validate")
    return data
