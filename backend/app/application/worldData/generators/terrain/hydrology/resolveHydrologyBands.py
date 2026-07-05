"""Hydrology band resolution — D HY-1c."""

from __future__ import annotations

import logging
from typing import Any

from app.application.jsonValidation import hydrology
from app.application.worldData.generators.terrain.hydrology.types import HydrologyBands
from app.dataModel.hydrology.lakes import HydrologyLakesPolicy
from app.dataModel.hydrology.rivers import HydrologyRiversPolicy
from app.dataModel.hydrology.seas import HydrologySeasPolicy

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

_CATEGORY_POJO: dict[str, type] = {
    "rivers": HydrologyRiversPolicy,
    "lakes":  HydrologyLakesPolicy,
    "seas":   HydrologySeasPolicy,
}


def _bands_from_section(section: Any, category: str) -> tuple[int | None, int | None]:
    pojo_cls = _CATEGORY_POJO.get(category)
    if pojo_cls is not None:
        if section is None:
            section = pojo_cls()
        elif isinstance(section, dict):
            section = pojo_cls.model_validate(section)
        bands = section.bands
        return bands.min, bands.max
    if isinstance(section, dict):
        bands = section.get("bands") or {}
        if isinstance(bands, dict):
            return bands.get("min"), bands.get("max")
        return None, None
    bands = getattr(section, "bands", None) if section is not None else None
    if bands is None:
        return None, None
    if isinstance(bands, dict):
        return bands.get("min"), bands.get("max")
    return getattr(bands, "min", None), getattr(bands, "max", None)


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
    raw_min, raw_max = _bands_from_section(section, category)
    result = clamp_bands(raw_min, raw_max)

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
