"""River type_classify — read explicit DB policy; legacy null → warn + canonical defaults (JV-7)."""

from __future__ import annotations

from typing import Any

from app.application.worldData.generators.climate.loggingHelpers import warn_once
from app.application.worldData.generators.masterData import hydrology, river_type_classify_defaults
from app.application.worldData.generators.terrain.hydrology.types import RiverTypeClassify


def _type_classify_from_defaults() -> RiverTypeClassify:
    pojo = river_type_classify_defaults()
    return RiverTypeClassify(
        mountain_min_source_z=int(pojo.mountain_min_source_z),
        path_mountain_fraction=float(pojo.path_mountain_fraction),
        rapid_drop_threshold_m=int(pojo.rapid_drop_threshold_m),
        mountain_bed_steepness_factor=float(pojo.mountain_bed_steepness_factor),
        foothill_gradient_threshold=float(pojo.foothill_gradient_threshold),
    )


def _pojo_to_runtime(pojo) -> RiverTypeClassify:
    defaults = river_type_classify_defaults()
    return RiverTypeClassify(
        mountain_min_source_z=int(
            pojo.mountain_min_source_z
            if pojo.mountain_min_source_z is not None
            else defaults.mountain_min_source_z
        ),
        path_mountain_fraction=float(
            pojo.path_mountain_fraction
            if pojo.path_mountain_fraction is not None
            else defaults.path_mountain_fraction
        ),
        rapid_drop_threshold_m=int(
            pojo.rapid_drop_threshold_m
            if pojo.rapid_drop_threshold_m is not None
            else defaults.rapid_drop_threshold_m
        ),
        mountain_bed_steepness_factor=float(
            pojo.mountain_bed_steepness_factor
            if pojo.mountain_bed_steepness_factor is not None
            else defaults.mountain_bed_steepness_factor
        ),
        foothill_gradient_threshold=float(
            pojo.foothill_gradient_threshold
            if pojo.foothill_gradient_threshold is not None
            else defaults.foothill_gradient_threshold
        ),
    )


def resolve_river_type_classify(world: Any) -> RiverTypeClassify:
    world_uid = getattr(world, "world_uid", "?")
    policy = hydrology(world)
    rivers = policy.default_rivers
    if rivers is None or rivers.type_classify is None:
        warn_once(
            world_uid,
            "missing_type_classify",
            "type_classify | world=%s default_rivers.type_classify missing; using dataModel defaults",
        )
        return _type_classify_from_defaults()

    pojo = rivers.type_classify
    raw = pojo.model_dump()
    defaults = river_type_classify_defaults().model_dump()
    null_keys = [k for k in defaults if raw.get(k) is None]
    if null_keys:
        warn_once(
            world_uid,
            "null_type_classify_fields",
            "type_classify | world=%s null fields %s; filling from dataModel defaults",
            null_keys,
        )

    return _pojo_to_runtime(pojo)
