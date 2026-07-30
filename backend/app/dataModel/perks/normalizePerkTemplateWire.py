"""Normalize perk template wire via POJO — tz_world_bundle WB-14."""

from __future__ import annotations

from typing import Any

from app.dataModel.perks.perkTemplateOutline import PerkTemplateOutline


def normalize_perk_template_body(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate + canonicalize wire (incl. legacy ``perk_uid``) → dict for ``WorldPerk``."""
    outline = PerkTemplateOutline.model_validate(raw)
    if not outline.template_uid or not outline.system_name or not outline.display_name:
        raise ValueError("PerkTemplateOutline identity incomplete after validate")
    return outline.model_dump(mode="json")
