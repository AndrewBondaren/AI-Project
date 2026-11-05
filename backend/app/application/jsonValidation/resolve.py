"""POJO resolve/normalize — single engine for import validator and runtime reads.

Typed schemas own required/default/nullable/enum contracts. No error defaults.
Contract: ``docs/tz_json_validation.md``.
"""

from __future__ import annotations

from dataclasses import replace
from copy import deepcopy
import json
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel, RootModel, ValidationError

from app.application.jsonValidation.resolution.diagnostics import (
    ResolveContext, ResolveMode, ResolveResult, StrictFieldError, UnresolvedModelError,
    log_issues, logger, log_resolve_transform, reject_unresolved, report_continuation, report_issues, report_unreported_issues,
)
from app.application.jsonValidation.resolution.partial import resolve_model_field, resolve_patch
from app.application.jsonValidation.resolution.references import reference_issues as _reference_issues
from app.application.jsonValidation.resolution.wireIssues import field_issue, pydantic_issues
from app.dataModel.validation.importIssues.wireLocation import WireLocation
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.fields.fieldBinding import bind_field
from app.dataModel.fields.validatedFieldPath import FieldSegment, ModelIdentity
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError

if TYPE_CHECKING:
    from app.application.jsonValidation.index.worldRegistryIndex import WorldRegistryIndex


def validate_contracts(model_cls: type[BaseModel], raw: Any, *, ctx: ResolveContext,
                       references: WorldRegistryIndex | None = None) -> None:
    value = resolve_model(model_cls, raw, ctx=ctx)
    if references is not None:
        issues = _reference_issues(value, ctx, references)
        if issues:
            reject_unresolved(ctx, issues)


def resolve_result(model_cls: type[BaseModel], raw: Any, *, ctx: ResolveContext | None = None,
                   references: WorldRegistryIndex | None = None) -> ResolveResult:
    ctx = ctx if ctx is not None else ResolveContext()
    try:
        value = resolve_model(model_cls, raw, ctx=ctx)
        if references is not None:
            issues = _reference_issues(value, ctx, references)
            if issues:
                reject_unresolved(ctx, issues)
        return ResolveResult(value)
    except UnresolvedModelError as exc:
        return ResolveResult(None, tuple(exc.issues))


def resolve_model[ModelT: BaseModel](
    model_cls: type[ModelT],
    raw: Any,
    *,
    label: str = "",
    ctx: ResolveContext | None = None,
    validation_context: dict | None = None,
) -> ModelT:
    """Validate the complete authored object; never construct an unchecked POJO.

    Pydantic owns aliases, field/model validators, presence and declared defaults.
    Passing a fieldwise reconstructed payload would bypass before validators and
    lose explicit null / model_fields_set used by cascade and room invariants.
    """
    active_ctx = ctx if ctx is not None else ResolveContext(
        location=WireLocation(parts=(label,) if label else ()), schema_id=getattr(model_cls, "SCHEMA_ID", None))
    if active_ctx.partial:
        raise TypeError("partial input is a patch; use resolve_patch and validate the merged object")
    context_data = {**(validation_context or {}), "validate_only": active_ctx.validate_only}
    defaults = getattr(model_cls, "WIRE_RUNTIME_DEFAULTS", ())
    if defaults and isinstance(raw, dict):
        result = _resolve_defaultable_wire(model_cls, raw, active_ctx, context_data, defaults)
    else:
        try:
            result = model_cls.model_validate(raw, by_name=True, context=context_data)
        except ValidationError as exc:
            reject_unresolved(active_ctx, pydantic_issues(active_ctx, model_cls, exc, raw=raw))
    log_resolve_transform(label or model_cls.__name__, raw, result, active_ctx)
    return result


def _resolve_defaultable_wire[ModelT: BaseModel](
    model_cls: type[ModelT], raw: dict, ctx: ResolveContext, context_data: dict,
    defaults: tuple[FieldRef, ...],
) -> ModelT:
    try:
        encoded = json.dumps(raw)
    except (TypeError, ValueError):
        # Internal callers may supply nested POJOs instead of a JSON document.
        try:
            return model_cls.model_validate(raw, by_name=True, context=context_data)
        except ValidationError as exc:
            reject_unresolved(ctx, pydantic_issues(ctx, model_cls, exc, raw=raw))
    try:
        return model_cls.model_validate_json(encoded, context=context_data)
    except ValidationError as exc:
        issues = pydantic_issues(ctx, model_cls, exc, raw=raw)
    if ctx.validate_only:
        reject_unresolved(ctx, issues)
    authorized = {(ModelIdentity.of(f.model), f.field) for f in map(bind_field, defaults)}
    repaired = deepcopy(raw)
    recovered = []
    for issue in issues:
        if not isinstance(issue, JsonFieldError):
            continue
        leaf = issue.path.segments[-1]
        if not isinstance(leaf, FieldSegment) or (leaf.owner, leaf.name) not in authorized:
            continue
        parent = repaired
        for part in issue.wire_path[:-1]:
            parent = parent[part]
        del parent[issue.wire_path[-1]]
        recovered.append(issue)
    if not recovered:
        reject_unresolved(ctx, issues)
    for issue in recovered:
        report_continuation(ctx, issue)
    try:
        return model_cls.model_validate_json(json.dumps(repaired), context=context_data)
    except ValidationError as remaining:
        reject_unresolved(ctx, pydantic_issues(ctx, model_cls, remaining, raw=repaired))


def resolve_root_list(
    registry_cls: type[RootModel],
    raw: Any,
    *,
    empty_factory: Any,
    label: str,
    world_uid: str | None = None,
    ctx: ResolveContext | None = None,
) -> RootModel:
    """A supplied registry is atomic: invalid rows never disappear."""
    active_ctx = ctx if ctx is not None else ResolveContext(
        location=WireLocation(parts=("worlds", world_uid, label) if world_uid else (label,)),
        schema_id=getattr(registry_cls, "SCHEMA_ID", None))
    if raw is None or (isinstance(raw, list) and not raw):
        return empty_factory()
    active_ctx = replace(active_ctx, partial=False)
    return resolve_model(registry_cls, raw, label=label, ctx=active_ctx)


def resolve_root_dict(
    registry_cls: type[RootModel],
    raw: Any,
    *,
    empty_factory: Any,
    label: str,
    world_uid: str | None = None,
    ctx: ResolveContext | None = None,
) -> RootModel:
    """A supplied registry replaces complete entries, even in a world patch."""
    active_ctx = ctx if ctx is not None else ResolveContext(
        location=WireLocation(parts=("worlds", world_uid, label) if world_uid else (label,)),
        schema_id=getattr(registry_cls, "SCHEMA_ID", None))
    if raw is None or (isinstance(raw, dict) and not raw):
        return empty_factory()
    active_ctx = replace(active_ctx, partial=False)
    return resolve_model(registry_cls, raw, label=label, ctx=active_ctx)
