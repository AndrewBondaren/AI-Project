"""Pure, scoped world-column validation using the shared POJO contracts."""

from copy import deepcopy
from dataclasses import replace
from typing import Any

from app.application.jsonValidation.resolve import (
    ResolveContext, UnresolvedModelError, resolve_model, resolve_model_field,
)
from app.application.jsonValidation.types import FieldPathError, ImportValidationError
from app.application.jsonValidation.worldSliceMerge import merge_world_slice
from app.application.jsonValidation.worldSlices import slice_for_world_key


def resolve_world_column(key: str, raw: Any, ctx: ResolveContext,
                         *, existing: Any = None) -> dict[str, Any]:
    """Resolve an atomic column; never return defaults for unrelated columns.

    A POJO model validator declares a whole-model invariant. For those slices
    the caller supplies the current row/mapping, projected by the POJO's wire
    helper. Independent fields use their original complete Pydantic schema.
    """
    world_slice = slice_for_world_key(key)
    if world_slice is None or not world_slice.facade:
        issue = FieldPathError(ctx.path_prefix + (key,),
            f"world column {key!r} is not a writable facade slice",
            code="NOT_WRITABLE_WORLD_COLUMN")
        ctx.report.issues.append(issue)
        raise ImportValidationError([issue])
    active = replace(ctx, partial=False, schema_id=world_slice.schema_id)
    raw = deepcopy(raw)
    try:
        if world_slice.wire_kind == "multi_column":
            pojo = world_slice.pojo_cls
            if (pojo.__pydantic_decorators__.model_validators
                    or pojo.__pydantic_decorators__.root_validators):
                if existing is None:
                    issue = FieldPathError(active.path_prefix + (key,),
                        "current slice values required for a model invariant",
                        schema_id=active.schema_id, code="WORLD_SLICE_CONTEXT_REQUIRED")
                    active.report.issues.append(issue)
                    raise ImportValidationError([issue])
                assert world_slice.wire_from_mapping is not None
                wire = deepcopy(world_slice.wire_from_mapping(existing))
                wire[key] = raw
                dump = resolve_model(pojo, wire, ctx=active).model_dump(mode="json")
                return {key: dump[key]}
            return {key: resolve_model_field(pojo, key, raw, ctx=active.child(key))}
        out = {key: raw}
        merge_world_slice(out, world_slice, active)
        return {key: out[key]}
    except UnresolvedModelError as exc:
        raise ImportValidationError(list(exc.issues)) from exc
