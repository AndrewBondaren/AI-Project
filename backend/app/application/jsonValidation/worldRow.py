"""``worlds`` row + bundle registries → typed dataModel POJOs."""

from __future__ import annotations

from typing import Any

from app.application.jsonValidation.resolve import resolve_model, resolve_root_dict, resolve_root_list
from app.dataModel.climate.worldClimateScalars import (
    WorldClimateScalars,
    climate_scalar_wire_from_mapping,
)
from app.dataModel.terrain.worldTerrainScalars import (
    WorldTerrainScalars,
    terrain_scalar_wire_from_mapping,
)
from app.dataModel import (
    WorldClimateZoneRegistry,
    WorldEconomyTierRegistry,
    WorldHydrology,
    WorldLocationMoodRegistry,
    WorldLocationTypeRegistry,
    WorldLoreRegistry,
    WorldMaterialRegistry,
    WorldRoadSettings,
    WorldRoomTypeRegistry,
    WorldTerrainCategoryRegistry,
    WorldTerrainRegistry,
    WorldWeatherTypeRegistry,
)
from app.dataModel.terrainMasks import WorldTerrainMasks
from app.application.jsonValidation.worldSlices import (
    climate_zone_wire_from_raw,
    location_type_wire_from_raw,
)
from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import (
    WorldConnectionTypeRegistry,
)
from app.dataModel.hydrology.rivers import RiverTypeClassify as PojoRiverTypeClassify
from app.dataModel.settlement.district.worldDistrictTemplateRegistry import WorldDistrictTemplateRegistry
from app.dataModel.settlement.settlement.worldCitySizeRegistry import WorldCitySizeRegistry
from app.dataModel.structure.barrier.worldBarrierTemplateRegistry import WorldBarrierTemplateRegistry
from app.dataModel.structure.building.worldBuildingTemplateRegistry import WorldBuildingTemplateRegistry

_DEFAULT_PRECIPITATION_LIQUID = WorldClimateScalars.canonical_defaults().precipitation_liquid
_ENGINE_ECONOMIC_TIERS = WorldEconomyTierRegistry.canonical_engine()
_ENGINE_MATERIALS = WorldMaterialRegistry.canonical_engine()


def _uid(world: Any) -> str:
    return str(getattr(world, "world_uid", "?"))


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


def terrain_masks(world: Any) -> WorldTerrainMasks:
    raw = getattr(world, "terrain_masks", None)
    if not raw:
        return WorldTerrainMasks.canonical_empty()
    return resolve_model(
        WorldTerrainMasks,
        raw,
        label=f"world={_uid(world)} terrain_masks",
    )


def terrain_masks_dict(world: Any) -> dict:
    return terrain_masks(world).model_dump(mode="json")


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
    wire = climate_zone_wire_from_raw(getattr(world, "climate_zone_registry", None))
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


def terrain_scalars(world: Any) -> WorldTerrainScalars:
    return resolve_model(
        WorldTerrainScalars,
        terrain_scalar_wire_from_mapping(world),
        label=f"world={_uid(world)} terrain_scalars",
    )


def default_precipitation_liquid() -> str:
    return _DEFAULT_PRECIPITATION_LIQUID


def legacy_standalone_water_material() -> str:
    liquids = materials_engine().liquid_keys()
    if liquids:
        return sorted(liquids)[0]
    return "water"


def city_sizes(world: Any) -> WorldCitySizeRegistry:
    return resolve_root_list(
        WorldCitySizeRegistry,
        getattr(world, "city_size_registry", None),
        empty_factory=WorldCitySizeRegistry.canonical_defaults,
        label="city_size_registry",
        world_uid=_uid(world),
    )


def district_templates(world: Any) -> WorldDistrictTemplateRegistry:
    """Canonical defaults merged with world overrides by ``system_name``."""
    by_name = {
        entry.system_name: entry
        for entry in WorldDistrictTemplateRegistry.canonical_defaults().root
    }
    raw = getattr(world, "district_template_registry", None)
    if raw:
        resolved = resolve_root_list(
            WorldDistrictTemplateRegistry,
            raw,
            empty_factory=WorldDistrictTemplateRegistry.canonical_defaults,
            label="district_template_registry",
            world_uid=_uid(world),
        )
        for entry in resolved.root:
            by_name[entry.system_name] = entry
    return WorldDistrictTemplateRegistry(list(by_name.values()))


def building_layout_templates(world: Any) -> list[dict]:
    """
    Merged building layout bodies — engine builtins + world rows.
    Layout JSON is not yet a single POJO row; registry merge stays wire-shaped.
    """
    from app.dataModel.structure.building.worldBuildingLayoutDefaults import canonical_defaults

    by_name: dict[str, dict] = {
        layout["system_name"]: dict(layout)
        for layout in canonical_defaults()
    }
    for row in getattr(world, "building_template_registry", None) or []:
        if not isinstance(row, dict):
            continue
        key = row.get("system_name") or row.get("system_template_uid")
        if key:
            by_name[str(key)] = row
    return list(by_name.values())


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


def connection_types(world: Any) -> WorldConnectionTypeRegistry:
    return resolve_root_list(
        WorldConnectionTypeRegistry,
        getattr(world, "connection_type_registry", None),
        empty_factory=WorldConnectionTypeRegistry.canonical_defaults,
        label="connection_type_registry",
        world_uid=_uid(world),
    )


def location_types(world: Any) -> WorldLocationTypeRegistry:
    wire = location_type_wire_from_raw(getattr(world, "location_type_registry", None))
    if wire is None:
        return WorldLocationTypeRegistry.canonical_defaults()
    return resolve_root_list(
        WorldLocationTypeRegistry,
        wire,
        empty_factory=WorldLocationTypeRegistry.canonical_defaults,
        label="location_type_registry",
        world_uid=_uid(world),
    )


def lore(world: Any) -> WorldLoreRegistry:
    return resolve_root_dict(
        WorldLoreRegistry,
        getattr(world, "lore_registry", None),
        empty_factory=WorldLoreRegistry.canonical_defaults,
        label="lore_registry",
        world_uid=_uid(world),
    )


def weather_types(world: Any) -> WorldWeatherTypeRegistry:
    return resolve_root_list(
        WorldWeatherTypeRegistry,
        getattr(world, "weather_type_registry", None),
        empty_factory=WorldWeatherTypeRegistry.canonical_defaults,
        label="weather_type_registry",
        world_uid=_uid(world),
    )


def terrain_categories(world: Any) -> WorldTerrainCategoryRegistry:
    return resolve_root_list(
        WorldTerrainCategoryRegistry,
        getattr(world, "terrain_category_registry", None),
        empty_factory=WorldTerrainCategoryRegistry.canonical_defaults,
        label="terrain_category_registry",
        world_uid=_uid(world),
    )


def room_types(world: Any) -> WorldRoomTypeRegistry:
    return resolve_root_list(
        WorldRoomTypeRegistry,
        getattr(world, "room_type_registry", None),
        empty_factory=WorldRoomTypeRegistry.canonical_defaults,
        label="room_type_registry",
        world_uid=_uid(world),
    )


def location_moods(world: Any) -> WorldLocationMoodRegistry:
    return resolve_root_list(
        WorldLocationMoodRegistry,
        getattr(world, "location_mood_registry", None),
        empty_factory=WorldLocationMoodRegistry.canonical_defaults,
        label="location_mood_registry",
        world_uid=_uid(world),
    )


def building_template_registry(world: Any) -> WorldBuildingTemplateRegistry:
    return resolve_root_list(
        WorldBuildingTemplateRegistry,
        getattr(world, "building_template_registry", None),
        empty_factory=WorldBuildingTemplateRegistry.canonical_defaults,
        label="building_template_registry",
        world_uid=_uid(world),
    )
