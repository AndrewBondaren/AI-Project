"""Import / CRUD normalize facade — strict → ``ImportValidationError``, grace → log only."""

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

    merge_facade_slices(out, ctx)

    errors: list[FieldPathError] = list(ctx.errors)
    if not errors:
        errors.extend(validate_ref_w(out, partial=partial))

    if errors:
        raise ImportValidationError(errors)

    return out
