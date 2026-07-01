"""
Parse `worlds.*` master-data through dataModel POJOs — generator contract layer.

Generators import from here, not raw `world.*_registry` dicts or jsonValidation defaults.

TODO: этому модулю не место в generators/ и не в dataModel.
Перенести в jsonValidation (валидатор / normalize): validate → fill defaults из
dataModel.canonical_* → отдать нормализованный master-data view генераторам.
Удалить generators/masterData/ после миграции импортов.
См. .cursor/plans/world-master-data-relocation.md
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from app.dataModel import (
    WorldClimateScalars,
    WorldClimateZoneRegistry,
    WorldEconomyTierRegistry,
    WorldHydrology,
    WorldMaterialRegistry,
    WorldRoadSettings,
    WorldTerrainRegistry,
)
from app.dataModel.hydrology.rivers import RiverTypeClassify as PojoRiverTypeClassify
from app.dataModel.structure.barrier.worldBarrierTemplateRegistry import WorldBarrierTemplateRegistry

logger = logging.getLogger(__name__)

_DEFAULT_PRECIPITATION_LIQUID = WorldClimateScalars.canonical_defaults().precipitation_liquid
_ENGINE_ECONOMIC_TIERS = WorldEconomyTierRegistry.canonical_engine()
_ENGINE_MATERIALS = WorldMaterialRegistry.canonical_engine()


def _world_uid(world: Any) -> str:
    return str(getattr(world, "world_uid", "?"))


def _parse_list_registry(
    model_cls: type,
    raw: Any,
    canonical_fn: Any,
    world: Any,
    label: str,
) -> Any:
    if not raw:
        return canonical_fn()
    try:
        return model_cls.model_validate(raw)
    except ValidationError as exc:
        logger.warning(
            "master_data | world=%s invalid %s (%s errors); using canonical defaults",
            _world_uid(world),
            label,
            exc.error_count(),
        )
        return canonical_fn()


def _climate_zone_wire(world: Any) -> list[dict] | None:
    raw = getattr(world, "climate_zone_registry", None)
    if not raw:
        return None
    if isinstance(raw, list):
        return [e for e in raw if isinstance(e, dict)]
    if isinstance(raw, dict):
        values = list(raw.values())
        if values and all(isinstance(v, dict) for v in values):
            return values
        if isinstance(raw, dict):
            return [raw]
    return None


def economic_tiers(world: Any) -> WorldEconomyTierRegistry:
    return _parse_list_registry(
        WorldEconomyTierRegistry,
        getattr(world, "economic_tier_registry", None),
        WorldEconomyTierRegistry.canonical_defaults,
        world,
        "economic_tier_registry",
    )


def economic_tier_rows(world: Any) -> list[dict]:
    return [e.model_dump() for e in economic_tiers(world).root]


def economic_tier_engine() -> WorldEconomyTierRegistry:
    return _ENGINE_ECONOMIC_TIERS


def materials(world: Any) -> WorldMaterialRegistry:
    return _parse_list_registry(
        WorldMaterialRegistry,
        getattr(world, "material_registry", None),
        WorldMaterialRegistry.canonical_defaults,
        world,
        "material_registry",
    )


def material_rows(world: Any) -> list[dict]:
    return [e.model_dump() for e in materials(world).root]


def materials_engine() -> WorldMaterialRegistry:
    return _ENGINE_MATERIALS


def terrain(world: Any) -> WorldTerrainRegistry:
    return _parse_list_registry(
        WorldTerrainRegistry,
        getattr(world, "terrain_registry", None),
        WorldTerrainRegistry.canonical_defaults,
        world,
        "terrain_registry",
    )


def terrain_rows(world: Any) -> list[dict]:
    return [e.model_dump() for e in terrain(world).root]


def terrain_system_keys(world: Any) -> set[str]:
    return {e.system_terrain for e in terrain(world).root}


def hydrology(world: Any) -> WorldHydrology:
    raw = getattr(world, "hydrology", None)
    if not raw:
        return WorldHydrology.canonical_empty()
    try:
        return WorldHydrology.model_validate(raw)
    except ValidationError as exc:
        logger.warning(
            "master_data | world=%s invalid hydrology (%s errors); using canonical_empty",
            _world_uid(world),
            exc.error_count(),
        )
        return WorldHydrology.canonical_empty()


def hydrology_dict(world: Any) -> dict:
    return hydrology(world).model_dump(mode="json")


def river_type_classify_defaults() -> PojoRiverTypeClassify:
    return WorldHydrology.canonical_empty().default_rivers.type_classify


def road_settings(world: Any) -> WorldRoadSettings:
    return _parse_list_registry(
        WorldRoadSettings,
        getattr(world, "road_settings", None),
        WorldRoadSettings.canonical_defaults,
        world,
        "road_settings",
    )


def road_settings_rows(world: Any) -> list[dict]:
    return [e.model_dump(by_alias=True) for e in road_settings(world).root]


def climate_zones(world: Any) -> WorldClimateZoneRegistry:
    wire = _climate_zone_wire(world)
    if wire is None:
        return WorldClimateZoneRegistry.canonical_defaults()
    return _parse_list_registry(
        WorldClimateZoneRegistry,
        wire,
        WorldClimateZoneRegistry.canonical_defaults,
        world,
        "climate_zone_registry",
    )


def climate_scalars(world: Any) -> WorldClimateScalars:
    payload = {
        "default_climate_zone": getattr(world, "default_climate_zone", None),
        "climate_temperature_peak_min": getattr(world, "climate_temperature_peak_min", None),
        "climate_temperature_peak_max": getattr(world, "climate_temperature_peak_max", None),
        "climate_pole_mode": getattr(world, "climate_pole_mode", None),
        "climate_pole_preset": getattr(world, "climate_pole_preset", None),
        "climate_local_influence_fraction": getattr(
            world, "climate_local_influence_fraction", None,
        ),
        "precipitation_liquid": getattr(world, "precipitation_liquid", None),
        "season_temp_offsets": getattr(world, "season_temp_offsets", None),
    }
    try:
        return WorldClimateScalars.model_validate(payload)
    except ValidationError:
        logger.warning(
            "master_data | world=%s invalid climate scalars; using canonical_defaults",
            _world_uid(world),
        )
        return WorldClimateScalars.canonical_defaults()


def default_precipitation_liquid() -> str:
    return _DEFAULT_PRECIPITATION_LIQUID


def legacy_standalone_water_material() -> str:
    liquids = materials_engine().liquid_keys()
    if liquids:
        return sorted(liquids)[0]
    return "water"


def barrier_template_defaults() -> list[dict]:
    reg = WorldBarrierTemplateRegistry.canonical_defaults()
    return [e.model_dump(mode="json") for e in reg.root]
