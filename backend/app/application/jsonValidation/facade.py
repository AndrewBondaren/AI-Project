"""Import / CRUD normalize facade — strict → ``ImportValidationError``, grace → log only."""

from __future__ import annotations

from typing import Any

from app.application.jsonValidation.resolve import ResolveContext, ResolveMode
from app.application.jsonValidation.index import validate_ref_w
from app.application.jsonValidation.types import FieldPathError, ImportValidationError
from app.application.jsonValidation.worldSliceMerge import merge_facade_slices


def normalize_world(data: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
    """Normalize ``worlds`` wire dict for import or CRUD write."""
    out = dict(data)
    if "fine_cells_per_map_cell" in out:
        out.pop("map_cell_size_m", None)
    elif "map_cell_size_m" in out:
        out["fine_cells_per_map_cell"] = out.pop("map_cell_size_m")
    ctx = ResolveContext(mode=ResolveMode.IMPORT, partial=partial)

    merge_facade_slices(out, ctx)

    errors: list[FieldPathError] = list(ctx.errors)
    if not errors:
        errors.extend(validate_ref_w(out, partial=partial))

    if errors:
        raise ImportValidationError(errors)

    return out
