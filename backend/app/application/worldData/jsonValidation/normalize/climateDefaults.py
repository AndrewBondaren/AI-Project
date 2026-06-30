"""Climate scalar normalize — docs/tz_json_validation.md JV-3."""

from __future__ import annotations

from typing import Any

from app.application.worldData.jsonValidation.types import ValidationIssue
from app.application.worldData.jsonValidation.validators._issues import error

SCHEMA_ID = "SCH-WORLD-CLIMATE-POLICY"


def normalize_world_climate_fields(world: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not isinstance(world, dict):
        return issues

    if world.get("climate_pole_mode") is None:
        world["climate_pole_mode"] = "autoresolve"
    if world.get("climate_pole_preset") is None:
        world["climate_pole_preset"] = "binary"
    if world.get("precipitation_liquid") is None:
        world["precipitation_liquid"] = "water"

    offsets = world.get("season_temp_offsets")
    if offsets is None:
        world["season_temp_offsets"] = {}
    elif not isinstance(offsets, dict):
        issues.append(error(
            SCHEMA_ID, "world.season_temp_offsets", "INVALID_TYPE",
            "season_temp_offsets must be an object",
        ))

    return issues
