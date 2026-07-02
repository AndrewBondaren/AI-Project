"""``worlds`` row + bundle registries → typed dataModel POJOs."""

from __future__ import annotations

from typing import Any

from app.application.jsonValidation.resolve import resolve_model, resolve_root_list
from app.dataModel.climate.worldClimateScalars import (
    WorldClimateScalars,
    climate_scalar_wire_from_mapping,
)
from app.dataModel import (
    WorldClimateZoneRegistry,
    WorldEconomyTierRegistry,
    WorldHydrology,
    WorldMaterialRegistry,
    WorldRoadSettings,
    WorldTerrainRegistry,
)
from app.dataModel.hydrology.rivers import RiverTypeClassify as PojoRiverTypeClassify
from app.dataModel.structure.barrier.worldBarrierTemplateRegistry import WorldBarrierTemplateRegistry

_DEFAULT_PRECIPITATION_LIQUID = WorldClimateScalars.canonical_defaults().precipitation_liquid
_ENGINE_ECONOMIC_TIERS = WorldEconomyTierRegistry.canonical_engine()
_ENGINE_MATERIALS = WorldMaterialRegistry.canonical_engine()


def _uid(world: Any) -> str:
    return str(getattr(world, "world_uid", "?"))


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
        return [raw]
    return None


def economic_tiers(world: Any) -> WorldEconomyTierRegistry:
    return resolve_root_list(
        WorldEconomyTierRegistry,
        getattr(world, "economic_tier_registry", None),
        empty_factory=WorldEconomyTierRegistry.canonical_defaults,
        label="economic_tier_registry",
        world_uid=_uid(world),
    )


def economic_tier_rows(world: Any) -> list[dict]:
    return [e.model_dump() for e in economic_tiers(world).root]


def economic_tier_engine() -> WorldEconomyTierRegistry:
    return _ENGINE_ECONOMIC_TIERS


def materials(world: Any) -> WorldMaterialRegistry:
    return resolve_root_list(
        WorldMaterialRegistry,
        getattr(world, "material_registry", None),
        empty_factory=WorldMaterialRegistry.canonical_defaults,
        label="material_registry",
        world_uid=_uid(world),
    )


def material_rows(world: Any) -> list[dict]:
    return [e.model_dump() for e in materials(world).root]


def materials_engine() -> WorldMaterialRegistry:
    return _ENGINE_MATERIALS


def terrain(world: Any) -> WorldTerrainRegistry:
    return resolve_root_list(
        WorldTerrainRegistry,
        getattr(world, "terrain_registry", None),
        empty_factory=WorldTerrainRegistry.canonical_defaults,
        label="terrain_registry",
        world_uid=_uid(world),
    )


def terrain_rows(world: Any) -> list[dict]:
    return [e.model_dump() for e in terrain(world).root]


def terrain_system_keys(world: Any) -> set[str]:
    return {e.system_terrain for e in terrain(world).root}


def hydrology(world: Any) -> WorldHydrology:
    raw = getattr(world, "hydrology", None)
    if not raw:
        return WorldHydrology.canonical_empty()
    return resolve_model(
        WorldHydrology,
        raw,
        label=f"world={_uid(world)} hydrology",
    )


def hydrology_dict(world: Any) -> dict:
    return hydrology(world).model_dump(mode="json")


def river_type_classify_defaults() -> PojoRiverTypeClassify:
    return WorldHydrology.canonical_empty().default_rivers.type_classify


def road_settings(world: Any) -> WorldRoadSettings:
    return resolve_root_list(
        WorldRoadSettings,
        getattr(world, "road_settings", None),
        empty_factory=WorldRoadSettings.canonical_defaults,
        label="road_settings",
        world_uid=_uid(world),
    )


def road_settings_rows(world: Any) -> list[dict]:
    return [e.model_dump(by_alias=True) for e in road_settings(world).root]


def climate_zones(world: Any) -> WorldClimateZoneRegistry:
    wire = _climate_zone_wire(world)
    if wire is None:
        return WorldClimateZoneRegistry.canonical_defaults()
    return resolve_root_list(
        WorldClimateZoneRegistry,
        wire,
        empty_factory=WorldClimateZoneRegistry.canonical_defaults,
        label="climate_zone_registry",
        world_uid=_uid(world),
    )


def climate_scalars(world: Any) -> WorldClimateScalars:
    return resolve_model(
        WorldClimateScalars,
        climate_scalar_wire_from_mapping(world),
        label=f"world={_uid(world)} climate_scalars",
    )


def default_precipitation_liquid() -> str:
    return _DEFAULT_PRECIPITATION_LIQUID


def legacy_standalone_water_material() -> str:
    liquids = materials_engine().liquid_keys()
    if liquids:
        return sorted(liquids)[0]
    return "water"


def barrier_templates(world: Any) -> WorldBarrierTemplateRegistry:
    """Canonical defaults merged with world overrides by ``system_type``."""
    by_type = {
        entry.system_type: entry
        for entry in WorldBarrierTemplateRegistry.canonical_defaults().root
    }
    raw = getattr(world, "barrier_template_registry", None)
    if raw:
        resolved = resolve_root_list(
            WorldBarrierTemplateRegistry,
            raw,
            empty_factory=WorldBarrierTemplateRegistry.canonical_defaults,
            label="barrier_template_registry",
            world_uid=_uid(world),
        )
        for entry in resolved.root:
            by_type[entry.system_type] = entry
    return WorldBarrierTemplateRegistry(list(by_type.values()))


def barrier_template_defaults() -> list[dict]:
    reg = WorldBarrierTemplateRegistry.canonical_defaults()
    return [e.model_dump(mode="json") for e in reg.root]
