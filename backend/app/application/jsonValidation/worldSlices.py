"""Registry of ``worlds`` master-data slices — ``docs/tz_json_validation.md`` § WorldSlice.

Catalog + runtime ``resolve_*_world``. Import merge → ``worldSliceMerge`` (T-29).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from app.application.jsonValidation.resolve import (
    resolve_model,
    resolve_root_dict,
    resolve_root_list,
)
from app.dataModel.climate.worldClimateScalars import (
    CLIMATE_SCALAR_WIRE_KEYS,
    WorldClimateScalars,
    climate_scalar_wire_from_mapping,
)
from app.dataModel.terrain.worldTerrainScalars import (
    TERRAIN_SCALAR_WIRE_KEYS,
    WorldTerrainScalars,
    terrain_scalar_wire_from_mapping,
)
from app.dataModel import (
    WorldClimateZoneRegistry,
    WorldEconomyTierRegistry,
    WorldHydrology,
    WorldLocationTypeRegistry,
    WorldLoreRegistry,
    WorldMaterialRegistry,
    WorldTerrainRegistry,
    WorldWeatherTypeRegistry,
)
from app.dataModel.terrainMasks import WorldTerrainMasks
from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import (
    WorldConnectionTypeRegistry,
)
from app.dataModel.roads.worldRoadSettings import WorldRoadSettings
from app.dataModel.settlement.district.worldDistrictTemplateRegistry import (
    WorldDistrictTemplateRegistry,
)
from app.dataModel.settlement.settlement.worldCitySizeRegistry import WorldCitySizeRegistry
from app.dataModel.settlement.settlement.worldLocationMoodRegistry import WorldLocationMoodRegistry
from app.dataModel.structure.barrier.worldBarrierTemplateRegistry import (
    WorldBarrierTemplateRegistry,
)
from app.dataModel.structure.building.worldBuildingTemplateRegistry import (
    WorldBuildingTemplateRegistry,
)
from app.dataModel.structure.room.worldRoomTypeRegistry import WorldRoomTypeRegistry
from app.dataModel.terrain.relief.worldReliefGradeObstacle import (
    RELIEF_OBSTACLE_SCALAR_WIRE_KEYS,
    WorldReliefGradeObstacleScalars,
    relief_obstacle_scalar_wire_from_mapping,
)
from app.dataModel.terrain.relief.worldCanalTemplateRegistry import (
    WorldCanalTemplateRegistry,
)
from app.dataModel.terrain.relief.worldReliefPickPolicy import WorldReliefPickPolicy
from app.dataModel.terrain.relief.worldReliefTemplateRegistry import (
    WorldReliefTemplateRegistry,
)
from app.dataModel.terrain.worldTerrainCategoryRegistry import WorldTerrainCategoryRegistry

WireKind = Literal["multi_column", "registry_list", "registry_dict", "json_blob"]


def climate_zone_wire_from_raw(raw: Any) -> list[dict] | None:
    """Normalize ``climate_zone_registry`` wire (array or legacy dict map).

    ``None`` → absent (caller may skip or use empty_factory).
    Empty list / empty dict → ``[]`` so import merge materializes canonical
    via ``resolve_root_list`` (same as other registry_list slices).
    """
    if raw is None:
        return None
    if isinstance(raw, list):
        return [entry for entry in raw if isinstance(entry, dict)]
    if isinstance(raw, dict):
        if not raw:
            return []
        values = list(raw.values())
        if values and all(isinstance(value, dict) for value in values):
            return values
        return [raw]
    return None


def registry_map_to_list(raw: Any, *, id_field: str) -> list[dict] | None:
    """Normalize legacy registry wire map ``{id: row}`` → list with ``id_field`` injected."""
    if not raw:
        return None
    if isinstance(raw, list):
        return [entry for entry in raw if isinstance(entry, dict)]
    if isinstance(raw, dict):
        rows: list[dict] = []
        for key, value in raw.items():
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault(id_field, key)
                rows.append(row)
        return rows
    return None


def location_type_wire_from_raw(raw: Any) -> list[dict] | None:
    return registry_map_to_list(raw, id_field="system_type")


@dataclass(frozen=True)
class WorldSlice:
    schema_id: str
    pojo_cls: type
    wire_kind: WireKind
    world_keys: tuple[str, ...]
    empty_factory: Callable[[], Any] | None = None
    wire_from_mapping: Callable[[Any], dict[str, Any]] | None = None
    wire_adapter: Callable[[Any], Any] | None = None
    facade: bool = False
    dump_by_alias: bool = False
    # Runtime: canonical_defaults ⊕ world rows keyed by entry attribute (T-29).
    runtime_merge_id_field: str | None = None


def _registry_slice(
    *,
    pojo_cls: type,
    world_key: str,
    facade: bool,
    wire_adapter: Callable[[Any], Any] | None = None,
    dump_by_alias: bool = False,
) -> WorldSlice:
    merge_id = getattr(pojo_cls, "RUNTIME_MERGE_ID_FIELD", None)
    return WorldSlice(
        schema_id=pojo_cls.SCHEMA_ID,
        pojo_cls=pojo_cls,
        wire_kind="registry_list",
        world_keys=(world_key,),
        empty_factory=pojo_cls.canonical_defaults,
        wire_adapter=wire_adapter,
        facade=facade,
        dump_by_alias=dump_by_alias,
        runtime_merge_id_field=merge_id if isinstance(merge_id, str) else None,
    )


def _registry_dict_slice(
    *,
    pojo_cls: type,
    world_key: str,
    facade: bool,
) -> WorldSlice:
    return WorldSlice(
        schema_id=pojo_cls.SCHEMA_ID,
        pojo_cls=pojo_cls,
        wire_kind="registry_dict",
        world_keys=(world_key,),
        empty_factory=pojo_cls.canonical_defaults,
        facade=facade,
    )


WORLD_SLICES: tuple[WorldSlice, ...] = (
    WorldSlice(
        schema_id=WorldClimateScalars.SCHEMA_ID,
        pojo_cls=WorldClimateScalars,
        wire_kind="multi_column",
        world_keys=tuple(CLIMATE_SCALAR_WIRE_KEYS),
        wire_from_mapping=climate_scalar_wire_from_mapping,
        facade=True,
    ),
    WorldSlice(
        schema_id=WorldTerrainScalars.SCHEMA_ID,
        pojo_cls=WorldTerrainScalars,
        wire_kind="multi_column",
        world_keys=tuple(TERRAIN_SCALAR_WIRE_KEYS),
        wire_from_mapping=terrain_scalar_wire_from_mapping,
        facade=True,
    ),
    WorldSlice(
        schema_id=WorldReliefGradeObstacleScalars.SCHEMA_ID,
        pojo_cls=WorldReliefGradeObstacleScalars,
        wire_kind="multi_column",
        world_keys=tuple(RELIEF_OBSTACLE_SCALAR_WIRE_KEYS),
        wire_from_mapping=relief_obstacle_scalar_wire_from_mapping,
        facade=True,
    ),
    _registry_slice(
        pojo_cls=WorldEconomyTierRegistry,
        world_key="economic_tier_registry",
        facade=True,
    ),
    _registry_slice(
        pojo_cls=WorldMaterialRegistry,
        world_key="material_registry",
        facade=True,
    ),
    _registry_slice(
        pojo_cls=WorldTerrainRegistry,
        world_key="terrain_registry",
        facade=True,
    ),
    _registry_slice(
        pojo_cls=WorldClimateZoneRegistry,
        world_key="climate_zone_registry",
        facade=True,
        wire_adapter=climate_zone_wire_from_raw,
    ),
    WorldSlice(
        schema_id=WorldHydrology.SCHEMA_ID,
        pojo_cls=WorldHydrology,
        wire_kind="json_blob",
        world_keys=("hydrology",),
        empty_factory=WorldHydrology.canonical_empty,
        facade=True,
    ),
    WorldSlice(
        schema_id=WorldTerrainMasks.SCHEMA_ID,
        pojo_cls=WorldTerrainMasks,
        wire_kind="json_blob",
        world_keys=("terrain_masks",),
        empty_factory=WorldTerrainMasks.canonical_empty,
        facade=True,
    ),
    _registry_slice(
        pojo_cls=WorldBarrierTemplateRegistry,
        world_key="barrier_template_registry",
        facade=True,
    ),
    _registry_slice(
        pojo_cls=WorldCitySizeRegistry,
        world_key="city_size_registry",
        facade=True,
    ),
    _registry_slice(
        pojo_cls=WorldDistrictTemplateRegistry,
        world_key="district_template_registry",
        facade=True,
    ),
    _registry_slice(
        pojo_cls=WorldRoadSettings,
        world_key="road_settings",
        facade=True,
        dump_by_alias=True,
    ),
    _registry_slice(
        pojo_cls=WorldConnectionTypeRegistry,
        world_key="connection_type_registry",
        facade=True,
    ),
    _registry_slice(
        pojo_cls=WorldLocationTypeRegistry,
        world_key="location_type_registry",
        facade=True,
        wire_adapter=location_type_wire_from_raw,
    ),
    _registry_dict_slice(
        pojo_cls=WorldLoreRegistry,
        world_key="lore_registry",
        facade=True,
    ),
    _registry_slice(
        pojo_cls=WorldWeatherTypeRegistry,
        world_key="weather_type_registry",
        facade=True,
    ),
    _registry_slice(
        pojo_cls=WorldTerrainCategoryRegistry,
        world_key="terrain_category_registry",
        facade=True,
    ),
    _registry_slice(
        pojo_cls=WorldRoomTypeRegistry,
        world_key="room_type_registry",
        facade=True,
    ),
    _registry_slice(
        pojo_cls=WorldLocationMoodRegistry,
        world_key="location_mood_registry",
        facade=True,
    ),
    _registry_slice(
        pojo_cls=WorldBuildingTemplateRegistry,
        world_key="building_template_registry",
        facade=True,
    ),
    _registry_slice(
        pojo_cls=WorldReliefTemplateRegistry,
        world_key="relief_template_registry",
        facade=True,
    ),
    _registry_slice(
        pojo_cls=WorldCanalTemplateRegistry,
        world_key="canal_template_registry",
        facade=True,
    ),
    WorldSlice(
        schema_id=WorldReliefPickPolicy.SCHEMA_ID,
        pojo_cls=WorldReliefPickPolicy,
        wire_kind="json_blob",
        world_keys=("relief_pick_policy",),
        empty_factory=WorldReliefPickPolicy.canonical_defaults,
        facade=True,
    ),
)

WORLD_SLICE_BY_KEY: dict[str, WorldSlice] = {
    key: world_slice
    for world_slice in WORLD_SLICES
    for key in world_slice.world_keys
}

WORLD_SLICE_BY_POJO: dict[type, WorldSlice] = {
    world_slice.pojo_cls: world_slice for world_slice in WORLD_SLICES
}


def slice_for_world_key(key: str) -> WorldSlice | None:
    return WORLD_SLICE_BY_KEY.get(key)


def slice_for_pojo(pojo_cls: type) -> WorldSlice | None:
    return WORLD_SLICE_BY_POJO.get(pojo_cls)


def _require_slice(pojo_cls: type, wire_kind: WireKind) -> WorldSlice:
    world_slice = slice_for_pojo(pojo_cls)
    if world_slice is None or world_slice.wire_kind != wire_kind:
        raise RuntimeError(
            f"no {wire_kind} WorldSlice registered for {pojo_cls.__name__}",
        )
    return world_slice


def slice_column_key(pojo_cls: type) -> str:
    """Primary ``worlds`` column for a registered slice (RELIEF-T-28 / T-37)."""
    world_slice = slice_for_pojo(pojo_cls)
    if world_slice is None or not world_slice.world_keys:
        raise RuntimeError(f"no WorldSlice registered for {pojo_cls.__name__}")
    return world_slice.world_keys[0]


def resolve_multi_column_world(
    world: Any,
    pojo_cls: type,
    *,
    label: str | None = None,
) -> Any:
    """Runtime resolve for ``multi_column`` slices — SoT = ``WORLD_SLICES``.

    Import/facade merge and generate use the same ``wire_from_mapping`` /
    ``pojo_cls`` (JV-SCALARS-2). Avoid hand-rolled resolve in ``worldRow``.
    """
    world_slice = _require_slice(pojo_cls, "multi_column")
    if world_slice.wire_from_mapping is None:
        raise RuntimeError(
            f"multi_column WorldSlice for {pojo_cls.__name__} missing wire_from_mapping",
        )
    resolve_label = label or f"world multi_column {world_slice.schema_id}"
    return resolve_model(
        pojo_cls,
        world_slice.wire_from_mapping(world),
        label=resolve_label,
    )


def resolve_registry_list_world(
    world: Any,
    pojo_cls: type,
    *,
    label: str | None = None,
    world_uid: str | None = None,
) -> Any:
    """Runtime resolve for ``registry_list`` slices — SoT = ``WORLD_SLICES`` (T-28).

    When ``WorldSlice.runtime_merge_id_field`` is set (T-29): return
    ``canonical_defaults`` ⊕ world rows keyed by that entry attribute.
    """
    world_slice = _require_slice(pojo_cls, "registry_list")
    if world_slice.empty_factory is None:
        raise RuntimeError(
            f"registry_list WorldSlice for {pojo_cls.__name__} missing empty_factory",
        )
    key = world_slice.world_keys[0]
    raw: Any = getattr(world, key, None)
    if world_slice.wire_adapter is not None:
        raw = world_slice.wire_adapter(raw)
    if world_slice.wire_adapter is not None and raw is None:
        resolved = world_slice.empty_factory()
    else:
        resolved = resolve_root_list(
            pojo_cls,
            raw,
            empty_factory=world_slice.empty_factory,
            label=label or key,
            world_uid=world_uid,
        )
    return _apply_runtime_canonical_merge(world_slice, resolved)


def _apply_runtime_canonical_merge(world_slice: WorldSlice, resolved: Any) -> Any:
    id_field = world_slice.runtime_merge_id_field
    if not id_field or world_slice.empty_factory is None:
        return resolved
    by_id: dict[Any, Any] = {
        getattr(entry, id_field): entry
        for entry in world_slice.empty_factory().root
    }
    for entry in resolved.root:
        by_id[getattr(entry, id_field)] = entry
    return world_slice.pojo_cls(list(by_id.values()))


def resolve_registry_dict_world(
    world: Any,
    pojo_cls: type,
    *,
    label: str | None = None,
    world_uid: str | None = None,
) -> Any:
    """Runtime resolve for ``registry_dict`` slices — SoT = ``WORLD_SLICES`` (T-28)."""
    world_slice = _require_slice(pojo_cls, "registry_dict")
    if world_slice.empty_factory is None:
        raise RuntimeError(
            f"registry_dict WorldSlice for {pojo_cls.__name__} missing empty_factory",
        )
    key = world_slice.world_keys[0]
    return resolve_root_dict(
        pojo_cls,
        getattr(world, key, None),
        empty_factory=world_slice.empty_factory,
        label=label or key,
        world_uid=world_uid,
    )


def resolve_json_blob_world(
    world: Any,
    pojo_cls: type,
    *,
    label: str | None = None,
) -> Any:
    """Runtime resolve for ``json_blob`` slices — SoT = ``WORLD_SLICES`` (T-28)."""
    world_slice = _require_slice(pojo_cls, "json_blob")
    key = world_slice.world_keys[0]
    raw = getattr(world, key, None)
    if not raw:
        if world_slice.empty_factory is None:
            raise RuntimeError(
                f"empty json_blob {pojo_cls.__name__} without empty_factory",
            )
        return world_slice.empty_factory()
    return resolve_model(
        pojo_cls,
        raw,
        label=label or f"world {key}",
    )


def facade_world_slices() -> tuple[WorldSlice, ...]:
    return tuple(sl for sl in WORLD_SLICES if sl.facade)
