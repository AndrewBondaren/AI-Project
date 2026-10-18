"""Import / CRUD facade: collect unresolved facts and reject before persistence."""

from __future__ import annotations

from typing import Any

from app.application.jsonValidation.resolve import ResolveContext, ResolveMode
from app.application.jsonValidation.index import validate_ref_w
from app.application.jsonValidation.types import FieldPathError, ImportValidationError
from app.application.jsonValidation.worldSliceMerge import merge_facade_slices
from app.application.jsonValidation.worldSlices import facade_world_slices


def merge_world_patch(existing: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Blob patches preserve absent nested fields; supplied registries replace."""
    def merge(base: Any, changes: Any) -> Any:
        if not isinstance(base, dict) or not isinstance(changes, dict):
            return changes
        result = dict(base)
        for key, value in changes.items():
            result[key] = merge(result.get(key), value)
        return result
    if "terrain_masks" in patch:
        from app.dataModel.terrainMasks.landcoverWire import normalize_landcover_wire
        patch = {**patch, "terrain_masks": normalize_landcover_wire(patch["terrain_masks"], partial=True)}
    out = {**existing, **patch}
    for sl in facade_world_slices():
        if sl.wire_kind == "json_blob":
            key = sl.world_keys[0]
            if key in patch:
                out[key] = merge(existing.get(key), patch[key])
    return out


def normalize_world(data: dict[str, Any], *, partial: bool = False,
                    ctx: ResolveContext | None = None) -> dict[str, Any]:
    """Normalize ``worlds`` wire dict for import or CRUD write."""
    out = dict(data)
    if "fine_cells_per_map_cell" in out:
        out.pop("map_cell_size_m", None)
    elif "map_cell_size_m" in out:
        out["fine_cells_per_map_cell"] = out.pop("map_cell_size_m")
    ctx = ctx if ctx is not None else ResolveContext(mode=ResolveMode.IMPORT, partial=partial)

    if partial and "terrain_masks" in out:
        from app.dataModel.terrainMasks.landcoverWire import normalize_landcover_wire
        try:
            out["terrain_masks"] = normalize_landcover_wire(out["terrain_masks"], partial=True)
        except ValueError:
            from dataclasses import replace
            from app.application.jsonValidation.resolve import resolve_model, UnresolvedModelError
            from app.dataModel.terrainMasks import WorldTerrainMasks
            try:
                resolve_model(WorldTerrainMasks, out["terrain_masks"],
                              ctx=replace(ctx.child("terrain_masks"), partial=False))
            except UnresolvedModelError:
                pass  # Preserve the shared report and reject below like other slices.

    merge_facade_slices(out, ctx)

    if partial and "terrain_masks" in out:
        from app.dataModel.terrainMasks.landcoverWire import landcover_patch_to_wire
        out["terrain_masks"] = landcover_patch_to_wire(out["terrain_masks"])

    errors: list[FieldPathError] = list(ctx.errors)
    if not errors:
        errors.extend(validate_ref_w(out, partial=partial))

    if errors:
        raise ImportValidationError(errors)

    if not partial and "terrain_masks" in out and "terrain_registry" in out:
        # Resolve alias hills before normalized canonical rows lose authored
        # field-presence information. Explicit authored registry hills still win.
        from app.application.jsonValidation.terrainHillRegistry import apply_landcover_policies
        from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
        from app.dataModel.terrainMasks import WorldTerrainMasks
        registry = apply_landcover_policies(WorldTerrainRegistry.model_validate(out["terrain_registry"]),
            WorldTerrainMasks.model_validate(out["terrain_masks"]).default_landcover,
            data.get("terrain_registry"))
        out["terrain_registry"] = registry.model_dump(mode="json")

    return out
