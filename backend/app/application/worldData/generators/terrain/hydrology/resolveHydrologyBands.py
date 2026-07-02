"""Hydrology band resolution — D HY-1c."""

from __future__ import annotations

import logging
from typing import Any

from app.application.jsonValidation import hydrology
from app.application.worldData.generators.terrain.hydrology.types import HydrologyBands

logger = logging.getLogger(__name__)

_BAND_MIN = 1
_BAND_MAX = 99

_CATEGORY_ATTR = {
    "rivers":    "default_rivers",
    "lakes":     "default_lakes",
    "seas":      "default_seas",
    "shore":     "default_shore",
    "landforms": "default_landforms",
}


def clamp_bands(raw_min: int | None, raw_max: int | None) -> HydrologyBands:
    lo = _BAND_MIN if raw_min is None else int(raw_min)
    hi = _BAND_MAX if raw_max is None else int(raw_max)
    lo = max(_BAND_MIN, min(lo, _BAND_MAX))
    hi = max(_BAND_MIN, min(hi, _BAND_MAX))
    if lo > hi:
        lo, hi = hi, lo
    return HydrologyBands(min=lo, max=hi)


def resolve_hydrology_bands(
    category: str,
    world: Any,
    local_profile: dict | None = None,
    *,
    world_uid: str | None = None,
) -> HydrologyBands:
    policy = hydrology(world)
    attr = _CATEGORY_ATTR.get(category, f"default_{category}")
    section = getattr(policy, attr, None)
    bands = section.bands if section is not None and section.bands is not None else None
    result = clamp_bands(
        bands.min if bands is not None else None,
        bands.max if bands is not None else None,
    )

    if local_profile and "bands" in local_profile:
        local = local_profile["bands"]
        local_result = clamp_bands(local.get("min"), local.get("max"))
        uid = world_uid or getattr(world, "world_uid", "?")
        logger.warning(
            "hydrology bands local override on world=%s category=%s — using local %s",
            uid, category, local_result,
        )
        return local_result

    return result
