"""Hydrology policy normalize — docs/tz_json_validation.md JV-3, U22."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.application.worldData.jsonValidation.types import ValidationIssue
from app.application.worldData.jsonValidation.validators._issues import error

SCHEMA_ID = "SCH-WORLD-HYDROLOGY"

# Canonical with resolveRiverTypeClassify._SCHEMA_DEFAULTS (U22); explicit in DB after import.
TYPE_CLASSIFY_DEFAULTS: dict[str, int | float] = {
    "mountain_min_source_z": 40,
    "path_mountain_fraction": 0.5,
    "rapid_drop_threshold_m": 3,
    "mountain_bed_steepness_factor": 1.5,
    "foothill_gradient_threshold": 0.12,
}


def _default_hydrology_blob() -> dict[str, Any]:
    return {
        "enabled": True,
        "default_shore": {
            "system_terrain": "shore",
            "system_material": "sand",
        },
        "default_rivers": {
            "enabled": True,
            "autoresolve": True,
            "bands": {"min": 1, "max": 5},
            "type_classify": dict(TYPE_CLASSIFY_DEFAULTS),
        },
        "default_lakes": {
            "enabled": True,
            "autoresolve": True,
            "bands": {"min": 1, "max": 5},
        },
        "default_seas": {
            "enabled": True,
            "autoresolve_coastal_sea": True,
            "autoresolve_open_ocean": True,
            "bands": {"min": 1, "max": 20},
        },
        "default_landforms": {
            "enabled": True,
            "autoresolve": True,
        },
        "materialize_named_locations": False,
    }


def _ensure_dict(parent: dict[str, Any], key: str) -> dict[str, Any]:
    child = parent.get(key)
    if not isinstance(child, dict):
        child = {}
        parent[key] = child
    return child


def normalize_world_hydrology(world: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    hydrology = world.get("hydrology")
    if hydrology is None:
        world["hydrology"] = deepcopy(_default_hydrology_blob())
        return issues
    if not isinstance(hydrology, dict):
        return [error(
            SCHEMA_ID, "world.hydrology", "INVALID_TYPE", "hydrology must be an object",
        )]

    if "enabled" not in hydrology:
        hydrology["enabled"] = True

    shore = _ensure_dict(hydrology, "default_shore")
    shore.setdefault("system_terrain", "shore")
    shore.setdefault("system_material", "sand")

    rivers = _ensure_dict(hydrology, "default_rivers")
    rivers.setdefault("enabled", True)
    rivers.setdefault("autoresolve", True)
    bands = _ensure_dict(rivers, "bands")
    bands.setdefault("min", 1)
    bands.setdefault("max", 5)
    tc = _ensure_dict(rivers, "type_classify")
    for key, default in TYPE_CLASSIFY_DEFAULTS.items():
        if tc.get(key) is None:
            tc[key] = default

    lakes = _ensure_dict(hydrology, "default_lakes")
    lakes.setdefault("enabled", True)
    lakes.setdefault("autoresolve", True)
    lb = _ensure_dict(lakes, "bands")
    lb.setdefault("min", 1)
    lb.setdefault("max", 5)

    seas = _ensure_dict(hydrology, "default_seas")
    seas.setdefault("enabled", True)
    seas.setdefault("autoresolve_coastal_sea", True)
    seas.setdefault("autoresolve_open_ocean", True)
    sb = _ensure_dict(seas, "bands")
    sb.setdefault("min", 1)
    sb.setdefault("max", 20)

    landforms = _ensure_dict(hydrology, "default_landforms")
    landforms.setdefault("enabled", True)
    landforms.setdefault("autoresolve", True)

    if "materialize_named_locations" not in hydrology:
        hydrology["materialize_named_locations"] = False

    return issues
