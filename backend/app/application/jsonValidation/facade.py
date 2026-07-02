"""Import / CRUD normalize facade — strict → ``ImportValidationError``, grace → log only."""

from __future__ import annotations

from typing import Any

from app.application.jsonValidation.resolve import (
    ResolveContext,
    ResolveMode,
    resolve_model,
    resolve_root_list,
)
from app.application.jsonValidation.types import ImportValidationError
from app.dataModel.climate.worldClimateScalars import (
    CLIMATE_SCALAR_WIRE_KEYS,
    WorldClimateScalars,
    climate_scalar_wire_from_mapping,
)
from app.dataModel import (
    WorldClimateZoneRegistry,
    WorldEconomyTierRegistry,
    WorldHydrology,
    WorldMaterialRegistry,
    WorldTerrainRegistry,
)

_LIST_REGISTRY_KEYS: tuple[tuple[str, type], ...] = (
    ("economic_tier_registry", WorldEconomyTierRegistry),
    ("material_registry", WorldMaterialRegistry),
    ("terrain_registry", WorldTerrainRegistry),
)


def _climate_zone_wire(raw: Any) -> list[dict] | None:
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


def _merge_climate_scalars(out: dict[str, Any], ctx: ResolveContext) -> None:
    if ctx.partial and not any(key in out for key in CLIMATE_SCALAR_WIRE_KEYS):
        return

    present_keys = {key for key in CLIMATE_SCALAR_WIRE_KEYS if key in out}
    wire = climate_scalar_wire_from_mapping(out)
    if ctx.partial:
        wire = {key: wire[key] for key in present_keys}
    resolved = resolve_model(
        WorldClimateScalars,
        wire,
        label="climate_scalars",
        ctx=ctx,
    )
    dump = resolved.model_dump(mode="json")
    keys_to_write = CLIMATE_SCALAR_WIRE_KEYS if not ctx.partial else present_keys
    for key in keys_to_write:
        if key in dump:
            out[key] = dump[key]


def _merge_list_registry(
    out: dict[str, Any],
    key: str,
    registry_cls: type,
    ctx: ResolveContext,
) -> None:
    if key not in out:
        return

    raw = out.get(key)
    empty_factory = registry_cls.canonical_defaults
    resolved = resolve_root_list(
        registry_cls,
        raw,
        empty_factory=empty_factory,
        label=key,
        ctx=ctx.child(key),
    )
    out[key] = [entry.model_dump(mode="json") for entry in resolved.root]


def _merge_climate_zone_registry(out: dict[str, Any], ctx: ResolveContext) -> None:
    key = "climate_zone_registry"
    if key not in out:
        return

    wire = _climate_zone_wire(out.get(key))
    if wire is None:
        return

    resolved = resolve_root_list(
        WorldClimateZoneRegistry,
        wire,
        empty_factory=WorldClimateZoneRegistry.canonical_defaults,
        label=key,
        ctx=ctx.child(key),
    )
    out[key] = [entry.model_dump(mode="json") for entry in resolved.root]


def _merge_hydrology(out: dict[str, Any], ctx: ResolveContext) -> None:
    key = "hydrology"
    if key not in out:
        return

    raw = out.get(key)
    if not raw:
        return

    resolved = resolve_model(
        WorldHydrology,
        raw,
        label=key,
        ctx=ctx.child(key),
    )
    out[key] = resolved.model_dump(mode="json")


def normalize_world(data: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
    """Normalize ``worlds`` wire dict for import or CRUD write."""
    out = dict(data)
    ctx = ResolveContext(mode=ResolveMode.IMPORT, partial=partial)

    _merge_climate_scalars(out, ctx)

    for key, registry_cls in _LIST_REGISTRY_KEYS:
        _merge_list_registry(out, key, registry_cls, ctx)

    _merge_climate_zone_registry(out, ctx)
    _merge_hydrology(out, ctx)

    if ctx.errors:
        raise ImportValidationError(ctx.errors)

    return out
