"""River type_classify defaults — D HY-1c, U22."""

from __future__ import annotations

from typing import Any

from app.application.worldData.generators.terrain.hydrology.types import RiverTypeClassify

_SCHEMA_DEFAULTS = RiverTypeClassify(
    mountain_min_source_z=40,
    path_mountain_fraction=0.5,
    rapid_drop_threshold_m=3,
    mountain_bed_steepness_factor=1.5,
    foothill_gradient_threshold=0.12,
)


def resolve_river_type_classify(world: Any) -> RiverTypeClassify:
    policy = getattr(world, "hydrology", None) or {}
    if not isinstance(policy, dict):
        return _SCHEMA_DEFAULTS

    rivers = policy.get("default_rivers") or {}
    raw = rivers.get("type_classify")
    if not isinstance(raw, dict):
        return _SCHEMA_DEFAULTS

    def _int(key: str, default: int) -> int:
        val = raw.get(key)
        return default if val is None else int(val)

    def _float(key: str, default: float) -> float:
        val = raw.get(key)
        return default if val is None else float(val)

    return RiverTypeClassify(
        mountain_min_source_z=_int("mountain_min_source_z", _SCHEMA_DEFAULTS.mountain_min_source_z),
        path_mountain_fraction=_float("path_mountain_fraction", _SCHEMA_DEFAULTS.path_mountain_fraction),
        rapid_drop_threshold_m=_int("rapid_drop_threshold_m", _SCHEMA_DEFAULTS.rapid_drop_threshold_m),
        mountain_bed_steepness_factor=_float(
            "mountain_bed_steepness_factor", _SCHEMA_DEFAULTS.mountain_bed_steepness_factor,
        ),
        foothill_gradient_threshold=_float(
            "foothill_gradient_threshold", _SCHEMA_DEFAULTS.foothill_gradient_threshold,
        ),
    )
