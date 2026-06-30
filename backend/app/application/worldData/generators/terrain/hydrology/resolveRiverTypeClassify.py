"""River type_classify — read explicit DB policy; legacy null → warn + canonical defaults (JV-7)."""

from __future__ import annotations

from typing import Any

from app.application.worldData.generators.climate.loggingHelpers import warn_once
from app.application.worldData.generators.terrain.hydrology.types import RiverTypeClassify
from app.application.worldData.jsonValidation.normalize.hydrologyDefaults import TYPE_CLASSIFY_DEFAULTS


def _type_classify_from_defaults() -> RiverTypeClassify:
    return RiverTypeClassify(
        mountain_min_source_z=int(TYPE_CLASSIFY_DEFAULTS["mountain_min_source_z"]),
        path_mountain_fraction=float(TYPE_CLASSIFY_DEFAULTS["path_mountain_fraction"]),
        rapid_drop_threshold_m=int(TYPE_CLASSIFY_DEFAULTS["rapid_drop_threshold_m"]),
        mountain_bed_steepness_factor=float(TYPE_CLASSIFY_DEFAULTS["mountain_bed_steepness_factor"]),
        foothill_gradient_threshold=float(TYPE_CLASSIFY_DEFAULTS["foothill_gradient_threshold"]),
    )


def resolve_river_type_classify(world: Any) -> RiverTypeClassify:
    world_uid = getattr(world, "world_uid", "?")
    policy = getattr(world, "hydrology", None) or {}
    if not isinstance(policy, dict):
        warn_once(
            world_uid,
            "missing_hydrology_policy",
            "type_classify | world=%s hydrology policy missing or invalid; using import defaults",
        )
        return _type_classify_from_defaults()

    rivers = policy.get("default_rivers") or {}
    raw = rivers.get("type_classify")
    if not isinstance(raw, dict):
        warn_once(
            world_uid,
            "missing_type_classify",
            "type_classify | world=%s default_rivers.type_classify missing; using import defaults",
        )
        return _type_classify_from_defaults()

    null_keys = [k for k in TYPE_CLASSIFY_DEFAULTS if raw.get(k) is None]
    if null_keys:
        warn_once(
            world_uid,
            "null_type_classify_fields",
            "type_classify | world=%s null fields %s; filling from import defaults",
            null_keys,
        )

    def _int(key: str) -> int:
        val = raw.get(key)
        return int(TYPE_CLASSIFY_DEFAULTS[key]) if val is None else int(val)

    def _float(key: str) -> float:
        val = raw.get(key)
        return float(TYPE_CLASSIFY_DEFAULTS[key]) if val is None else float(val)

    return RiverTypeClassify(
        mountain_min_source_z=_int("mountain_min_source_z"),
        path_mountain_fraction=_float("path_mountain_fraction"),
        rapid_drop_threshold_m=_int("rapid_drop_threshold_m"),
        mountain_bed_steepness_factor=_float("mountain_bed_steepness_factor"),
        foothill_gradient_threshold=_float("foothill_gradient_threshold"),
    )
