"""``worlds`` row + bundle registries → typed dataModel POJOs.

Runtime DX accessors. Slice-backed resolve → ``worldSlices.resolve_*_world``
(RELIEF-T-28); column names from ``WORLD_SLICES`` (T-37).
"""

from __future__ import annotations

from typing import Any

from app.application.jsonValidation.worldSlices import (
    resolve_json_blob_world,
    resolve_multi_column_world,
    resolve_registry_dict_world,
    resolve_registry_list_world,
    slice_column_key,
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
from app.dataModel.climate.worldClimateScalars import WorldClimateScalars
from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import (
    WorldConnectionTypeRegistry,
)
from app.dataModel.hydrology.rivers import RiverTypeClassify as PojoRiverTypeClassify
from app.dataModel.settlement.district.worldDistrictTemplateRegistry import (
    WorldDistrictTemplateRegistry,
)
from app.dataModel.settlement.settlement.worldCitySizeRegistry import WorldCitySizeRegistry
from app.dataModel.structure.barrier.worldBarrierTemplateRegistry import (
    WorldBarrierTemplateRegistry,
)
from app.dataModel.structure.building.worldBuildingTemplateRegistry import (
    WorldBuildingTemplateRegistry,
)
from app.dataModel.terrain.relief.enums import ReliefGradeObstaclePolicy
from app.dataModel.terrain.relief.worldCanalTemplateRegistry import WorldCanalTemplateRegistry
from app.dataModel.terrain.relief.worldReliefGradeObstacle import (
    WorldReliefGradeObstacleScalars,
)
from app.dataModel.terrain.relief.worldReliefPickPolicy import WorldReliefPickPolicy
from app.dataModel.terrain.relief.worldReliefTemplateRegistry import (
    WorldReliefTemplateRegistry,
)
from app.dataModel.terrain.worldTerrainScalars import WorldTerrainScalars
from app.dataModel.terrainMasks import WorldTerrainMasks

_DEFAULT_PRECIPITATION_LIQUID = WorldClimateScalars.canonical_defaults().precipitation_liquid
_ENGINE_ECONOMIC_TIERS = WorldEconomyTierRegistry.canonical_engine()
_ENGINE_MATERIALS = WorldMaterialRegistry.canonical_engine()


def _uid(world: Any) -> str:
    return str(getattr(world, "world_uid", "?"))


def economic_tiers(world: Any) -> WorldEconomyTierRegistry:
    return resolve_registry_list_world(
        world, WorldEconomyTierRegistry, world_uid=_uid(world),
    )


def economic_tier_rows(world: Any) -> list[dict]:
    return [e.model_dump() for e in economic_tiers(world).root]


def economic_tier_engine() -> WorldEconomyTierRegistry:
    return _ENGINE_ECONOMIC_TIERS


def materials(world: Any) -> WorldMaterialRegistry:
    return resolve_registry_list_world(
        world, WorldMaterialRegistry, world_uid=_uid(world),
    )


def material_rows(world: Any) -> list[dict]:
    return [e.model_dump() for e in materials(world).root]


def materials_engine() -> WorldMaterialRegistry:
    return _ENGINE_MATERIALS


def terrain(world: Any) -> WorldTerrainRegistry:
    return resolve_registry_list_world(
        world, WorldTerrainRegistry, world_uid=_uid(world),
    )


def terrain_rows(world: Any) -> list[dict]:
    return [e.model_dump() for e in terrain(world).root]


def terrain_system_keys(world: Any) -> set[str]:
    return {e.system_terrain for e in terrain(world).root}


def hydrology(world: Any) -> WorldHydrology:
    return resolve_json_blob_world(
        world, WorldHydrology, label=f"world={_uid(world)} hydrology",
    )


def hydrology_dict(world: Any) -> dict:
    return hydrology(world).model_dump(mode="json")


def terrain_masks(world: Any) -> WorldTerrainMasks:
    return resolve_json_blob_world(
        world, WorldTerrainMasks, label=f"world={_uid(world)} terrain_masks",
    )


def terrain_masks_dict(world: Any) -> dict:
    return terrain_masks(world).model_dump(mode="json")


def river_type_classify_defaults() -> PojoRiverTypeClassify:
    return WorldHydrology.canonical_empty().default_rivers.type_classify


def road_settings(world: Any) -> WorldRoadSettings:
    return resolve_registry_list_world(
        world, WorldRoadSettings, world_uid=_uid(world),
    )


def road_settings_rows(world: Any) -> list[dict]:
    return [e.model_dump(by_alias=True) for e in road_settings(world).root]


def climate_zones(world: Any) -> WorldClimateZoneRegistry:
    return resolve_registry_list_world(
        world, WorldClimateZoneRegistry, world_uid=_uid(world),
    )


def climate_scalars(world: Any) -> WorldClimateScalars:
    return resolve_multi_column_world(
        world,
        WorldClimateScalars,
        label=f"world={_uid(world)} climate_scalars",
    )


def terrain_scalars(world: Any) -> WorldTerrainScalars:
    return resolve_multi_column_world(
        world,
        WorldTerrainScalars,
        label=f"world={_uid(world)} terrain_scalars",
    )


def default_precipitation_liquid() -> str:
    return _DEFAULT_PRECIPITATION_LIQUID


def city_sizes(world: Any) -> WorldCitySizeRegistry:
    return resolve_registry_list_world(
        world, WorldCitySizeRegistry, world_uid=_uid(world),
    )


def district_templates(world: Any) -> WorldDistrictTemplateRegistry:
    """Canonical ⊕ world by ``RUNTIME_MERGE_ID_FIELD`` (T-29)."""
    return resolve_registry_list_world(
        world, WorldDistrictTemplateRegistry, world_uid=_uid(world),
    )

def building_layout_templates(world: Any) -> list[dict]:
    """
    Merged building layout bodies — engine builtins + world rows.
    Layout JSON is not yet a single POJO row; registry merge stays wire-shaped.
    """
    from app.dataModel.structure.building.worldBuildingLayoutDefaults import (
        canonical_defaults,
    )

    by_name: dict[str, dict] = {
        layout["system_name"]: dict(layout)
        for layout in canonical_defaults()
    }
    col = slice_column_key(WorldBuildingTemplateRegistry)
    for row in getattr(world, col, None) or []:
        if not isinstance(row, dict):
            continue
        key = row.get("system_name") or row.get("system_template_uid")
        if key:
            by_name[str(key)] = row
    return list(by_name.values())


def barrier_templates(world: Any) -> WorldBarrierTemplateRegistry:
    """Canonical ⊕ world by ``RUNTIME_MERGE_ID_FIELD`` (T-29)."""
    return resolve_registry_list_world(
        world, WorldBarrierTemplateRegistry, world_uid=_uid(world),
    )

def barrier_template_defaults() -> list[dict]:
    reg = WorldBarrierTemplateRegistry.canonical_defaults()
    return [e.model_dump(mode="json") for e in reg.root]


def connection_types(world: Any) -> WorldConnectionTypeRegistry:
    return resolve_registry_list_world(
        world, WorldConnectionTypeRegistry, world_uid=_uid(world),
    )


def location_types(world: Any) -> WorldLocationTypeRegistry:
    return resolve_registry_list_world(
        world, WorldLocationTypeRegistry, world_uid=_uid(world),
    )


def lore(world: Any) -> WorldLoreRegistry:
    return resolve_registry_dict_world(
        world, WorldLoreRegistry, world_uid=_uid(world),
    )


def weather_types(world: Any) -> WorldWeatherTypeRegistry:
    return resolve_registry_list_world(
        world, WorldWeatherTypeRegistry, world_uid=_uid(world),
    )


def terrain_categories(world: Any) -> WorldTerrainCategoryRegistry:
    return resolve_registry_list_world(
        world, WorldTerrainCategoryRegistry, world_uid=_uid(world),
    )


def room_types(world: Any) -> WorldRoomTypeRegistry:
    return resolve_registry_list_world(
        world, WorldRoomTypeRegistry, world_uid=_uid(world),
    )


def location_moods(world: Any) -> WorldLocationMoodRegistry:
    return resolve_registry_list_world(
        world, WorldLocationMoodRegistry, world_uid=_uid(world),
    )


def building_template_registry(world: Any) -> WorldBuildingTemplateRegistry:
    return resolve_registry_list_world(
        world, WorldBuildingTemplateRegistry, world_uid=_uid(world),
    )


def relief_template_registry(world: Any) -> WorldReliefTemplateRegistry:
    return resolve_registry_list_world(
        world, WorldReliefTemplateRegistry, world_uid=_uid(world),
    )


def canal_templates(world: Any) -> WorldCanalTemplateRegistry:
    """World ``canal_template_registry`` (R36q); empty → no entries."""
    return resolve_registry_list_world(
        world, WorldCanalTemplateRegistry, world_uid=_uid(world),
    )


def relief_pick_policy(world: Any) -> WorldReliefPickPolicy:
    return resolve_json_blob_world(world, WorldReliefPickPolicy)


def relief_obstacle_scalars(world: Any) -> WorldReliefGradeObstacleScalars:
    return resolve_multi_column_world(
        world,
        WorldReliefGradeObstacleScalars,
        label=f"world={_uid(world)} relief_obstacle_scalars",
    )


def relief_grade_obstacle_policy(world: Any) -> ReliefGradeObstaclePolicy:
    """World R36n setting; missing/NULL → ``truncate_skip``."""
    return relief_obstacle_scalars(world).relief_grade_obstacle_policy
