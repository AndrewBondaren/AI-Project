"""Registry of ``worlds`` master-data slices — ``docs/tz_json_validation.md`` § WorldSlice."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from app.application.jsonValidation.resolve import (
    ResolveContext,
    resolve_model,
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
    WorldMaterialRegistry,
    WorldTerrainRegistry,
)
from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import (
    WorldConnectionTypeRegistry,
)
from app.dataModel.roads.worldRoadSettings import WorldRoadSettings
from app.dataModel.settlement.district.worldDistrictTemplateRegistry import (
    WorldDistrictTemplateRegistry,
)
from app.dataModel.settlement.settlement.worldCitySizeRegistry import WorldCitySizeRegistry
from app.dataModel.structure.barrier.worldBarrierTemplateRegistry import (
    WorldBarrierTemplateRegistry,
)

WireKind = Literal["multi_column", "registry_list", "json_blob"]


def climate_zone_wire_from_raw(raw: Any) -> list[dict] | None:
    """Normalize ``climate_zone_registry`` wire (array or legacy dict map)."""
    if not raw:
        return None
    if isinstance(raw, list):
        return [entry for entry in raw if isinstance(entry, dict)]
    if isinstance(raw, dict):
        values = list(raw.values())
        if values and all(isinstance(value, dict) for value in values):
            return values
        return [raw]
    return None


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


def _registry_slice(
    *,
    pojo_cls: type,
    world_key: str,
    facade: bool,
    wire_adapter: Callable[[Any], Any] | None = None,
    dump_by_alias: bool = False,
) -> WorldSlice:
    return WorldSlice(
        schema_id=pojo_cls.SCHEMA_ID,
        pojo_cls=pojo_cls,
        wire_kind="registry_list",
        world_keys=(world_key,),
        empty_factory=pojo_cls.canonical_defaults,
        wire_adapter=wire_adapter,
        facade=facade,
        dump_by_alias=dump_by_alias,
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
        facade=False,
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
        facade=True,
    ),
    _registry_slice(
        pojo_cls=WorldBarrierTemplateRegistry,
        world_key="barrier_template_registry",
        facade=False,
    ),
    _registry_slice(
        pojo_cls=WorldCitySizeRegistry,
        world_key="city_size_registry",
        facade=False,
    ),
    _registry_slice(
        pojo_cls=WorldDistrictTemplateRegistry,
        world_key="district_template_registry",
        facade=False,
    ),
    _registry_slice(
        pojo_cls=WorldRoadSettings,
        world_key="road_settings",
        facade=False,
        dump_by_alias=True,
    ),
    _registry_slice(
        pojo_cls=WorldConnectionTypeRegistry,
        world_key="connection_type_registry",
        facade=False,
    ),
)

WORLD_SLICE_BY_KEY: dict[str, WorldSlice] = {
    key: world_slice
    for world_slice in WORLD_SLICES
    for key in world_slice.world_keys
}


def slice_for_world_key(key: str) -> WorldSlice | None:
    return WORLD_SLICE_BY_KEY.get(key)


def facade_world_slices() -> tuple[WorldSlice, ...]:
    return tuple(sl for sl in WORLD_SLICES if sl.facade)


def _slice_ctx(ctx: ResolveContext, world_slice: WorldSlice) -> ResolveContext:
    return ResolveContext(
        mode=ctx.mode,
        partial=ctx.partial,
        path_prefix=ctx.path_prefix,
        errors=ctx.errors,
        schema_id=world_slice.schema_id,
    )


def _merge_multi_column(
    out: dict[str, Any],
    world_slice: WorldSlice,
    ctx: ResolveContext,
) -> None:
    assert world_slice.wire_from_mapping is not None
    column_keys = frozenset(world_slice.world_keys)
    if ctx.partial and not any(key in out for key in column_keys):
        return

    present_keys = {key for key in column_keys if key in out}
    wire = world_slice.wire_from_mapping(out)
    if ctx.partial:
        wire = {key: wire[key] for key in present_keys}
    resolved = resolve_model(
        world_slice.pojo_cls,
        wire,
        label=world_slice.schema_id,
        ctx=ctx,
    )
    dump = resolved.model_dump(mode="json")
    keys_to_write = column_keys if not ctx.partial else present_keys
    for key in keys_to_write:
        if key in dump:
            out[key] = dump[key]


def _merge_registry_list(
    out: dict[str, Any],
    world_slice: WorldSlice,
    ctx: ResolveContext,
) -> None:
    key = world_slice.world_keys[0]
    if key not in out:
        return

    assert world_slice.empty_factory is not None
    raw = out.get(key)
    if world_slice.wire_adapter is not None:
        raw = world_slice.wire_adapter(raw)
        if raw is None:
            return

    resolved = resolve_root_list(
        world_slice.pojo_cls,
        raw,
        empty_factory=world_slice.empty_factory,
        label=key,
        ctx=ctx.child(key),
    )
    dump_kw: dict[str, Any] = {"mode": "json"}
    if world_slice.dump_by_alias:
        dump_kw["by_alias"] = True
    out[key] = [entry.model_dump(**dump_kw) for entry in resolved.root]


def _merge_json_blob(
    out: dict[str, Any],
    world_slice: WorldSlice,
    ctx: ResolveContext,
) -> None:
    key = world_slice.world_keys[0]
    if key not in out:
        return

    raw = out.get(key)
    if not raw:
        return

    resolved = resolve_model(
        world_slice.pojo_cls,
        raw,
        label=key,
        ctx=ctx.child(key),
    )
    out[key] = resolved.model_dump(mode="json")


def merge_world_slice(
    out: dict[str, Any],
    world_slice: WorldSlice,
    ctx: ResolveContext,
) -> None:
    if not world_slice.facade:
        return

    slice_ctx = _slice_ctx(ctx, world_slice)
    if world_slice.wire_kind == "multi_column":
        _merge_multi_column(out, world_slice, slice_ctx)
    elif world_slice.wire_kind == "registry_list":
        _merge_registry_list(out, world_slice, slice_ctx)
    elif world_slice.wire_kind == "json_blob":
        _merge_json_blob(out, world_slice, slice_ctx)


def merge_facade_slices(out: dict[str, Any], ctx: ResolveContext) -> None:
    for world_slice in facade_world_slices():
        merge_world_slice(out, world_slice, ctx)
