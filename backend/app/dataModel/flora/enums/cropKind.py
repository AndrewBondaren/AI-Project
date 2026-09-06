"""Wire ``crop_kind`` — ENUM-E how a crop is grown. tz_flora.md § crops_type."""

from __future__ import annotations

from enum import StrEnum


class CropKind(StrEnum):
    """How this crop is farmed. N+1 instances are ``system_crop`` rows."""

    GRAIN = "grain"
    VEGETABLE = "vegetable"
    FRUIT = "fruit"
    FIBER = "fiber"
    FODDER = "fodder"
