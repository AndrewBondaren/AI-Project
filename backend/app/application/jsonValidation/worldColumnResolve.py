"""Pure, scoped world-column validation using the shared POJO contracts."""

from copy import deepcopy
from dataclasses import replace
from typing import Any

from pydantic import BaseModel

from app.application.jsonValidation.resolve import (
    ResolveContext, UnresolvedModelError, field_issue, report_issues, resolve_model, resolve_model_field,
)
from app.application.jsonValidation.types import ImportValidationError
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue
from app.application.jsonValidation.worldSliceMerge import merge_world_slice
from app.application.jsonValidation.worldSlices import slice_for_world_key


def _pojo_of(cls: type) -> type[BaseModel] | None:
    return cls if issubclass(cls, BaseModel) else None


def resolve_world_column(key: str, raw: Any, ctx: ResolveContext,
                         *, existing: Any = None) -> dict[str, Any]:
    """Resolve an atomic column; never return defaults for unrelated columns.

    A POJO model validator declares a whole-model invariant. For those slices
    the caller supplies the current row/mapping, projected by the POJO's wire
    helper. Independent fields use their original complete Pydantic schema.
    """
    world_slice = slice_for_world_key(key)
    if world_slice is None or not world_slice.facade:
        issue = WireShapeIssue(code=JsonValidationCode.NOT_WRITABLE_WORLD_COLUMN, location=ctx.location.child(key),
                               message=f"world column {key!r} is not a writable facade slice")
        report_issues(ctx, [issue])
        raise ImportValidationError([issue])
    active = replace(ctx, partial=False, schema_id=world_slice.schema_id)
    raw = deepcopy(raw)
    try:
        if world_slice.wire_kind == "multi_column":
            pojo = world_slice.pojo_cls
            if (pojo.__pydantic_decorators__.model_validators
                    or pojo.__pydantic_decorators__.root_validators):
                if existing is None:
                    issue = field_issue(active, pojo, (key,),
                        "current slice values required for a model invariant",
                        JsonValidationCode.WORLD_SLICE_CONTEXT_REQUIRED)
                    report_issues(active, [issue])
                    raise ImportValidationError([issue])
                assert world_slice.wire_from_mapping is not None
                wire = deepcopy(world_slice.wire_from_mapping(existing))
                wire[key] = raw
                dump = resolve_model(pojo, wire, ctx=active).model_dump(mode="json")
                return {key: dump[key]}
            return {key: resolve_model_field(pojo, key, raw, ctx=active)}
        out = {key: raw}
        merge_world_slice(out, world_slice, active)
        return {key: out[key]}
    except UnresolvedModelError as exc:
        raise ImportValidationError(list(exc.issues)) from exc
    except ValueError as exc:
        issue = field_issue(active, _pojo_of(world_slice.pojo_cls), (key,), str(exc),
                            JsonValidationCode.VALIDATION_ERROR)
        report_issues(active, [issue])
        raise ImportValidationError([issue]) from exc
