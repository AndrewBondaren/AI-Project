"""POJO resolve/normalize — single engine for import validator and runtime reads.

Typed schemas own required/default/nullable/enum contracts. No error defaults.
Contract: ``docs/tz_json_validation.md``.
"""

from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, NoReturn, TYPE_CHECKING

from pydantic import BaseModel, RootModel, ValidationError
from pydantic_core import SchemaValidator, core_schema
from functools import lru_cache

from app.application.jsonValidation.types import FieldPathError, ResolveReport
from app.dataModel.registryKey import registry_key_target

if TYPE_CHECKING:
    from app.application.jsonValidation.index.worldRegistryIndex import WorldRegistryIndex

logger = logging.getLogger(__name__)


class ResolveMode(StrEnum):
    RUNTIME = "runtime"
    IMPORT = "import"


@dataclass
class ResolveContext:
    mode: ResolveMode = ResolveMode.RUNTIME
    partial: bool = False
    path_prefix: tuple[str | int, ...] = ()
    report: ResolveReport = field(default_factory=ResolveReport)
    schema_id: str | None = None
    validate_only: bool = False

    @property
    def errors(self) -> list[FieldPathError]:
        """Compatibility view for existing aggregators; the report owns facts."""
        return self.report.issues

    @classmethod
    def for_import(cls, *, validate_only: bool = False) -> ResolveContext:
        """The application entry owns the request policy; children inherit it."""
        # IMPORT is the legacy wire interpretation, identical for preview/apply.
        # Only the explicit flag controls the reaction to new-contract facts.
        return cls(mode=ResolveMode.IMPORT, validate_only=validate_only)

    def child(self, segment: str | int) -> ResolveContext:
        return ResolveContext(
            mode=self.mode,
            validate_only=self.validate_only,
            partial=self.partial,
            path_prefix=self.path_prefix + (segment,),
            report=self.report,
            schema_id=self.schema_id,
        )


class StrictFieldError(ValueError):
    def __init__(self, path: tuple[str | int, ...], detail: str) -> None:
        self.path = path
        self.detail = detail
        super().__init__(
            f"{'.'.join(str(part) for part in path)}: {detail}" if path else detail,
        )


class UnresolvedModelError(StrictFieldError):
    """No valid POJO exists. Never substitute this outcome with None/default."""

    def __init__(self, issues: list[FieldPathError]) -> None:
        self.issues = issues
        super().__init__(issues[0].path, issues[0].message)


@dataclass(frozen=True)
class ResolveResult:
    value: BaseModel | None
    issues: tuple[FieldPathError, ...] = ()

    @property
    def resolved(self) -> bool:
        return self.value is not None


def reject_unresolved(ctx: ResolveContext, issues: list[FieldPathError]) -> NoReturn:
    """One reaction point for structured facts from wire/domain checks."""
    ctx.errors.extend(issues)
    if not ctx.validate_only:
        for issue in issues:
            logger.warning("json_validation | WarningError | path=%s code=%s | %s",
                           issue.path, issue.code, issue.message)
    raise UnresolvedModelError(issues)


def _model_fields_schema(schema: dict, definitions: list[dict]) -> dict:
    while schema["type"] != "model-fields":
        if schema["type"] == "definition-ref":
            schema = next(item for item in definitions if item.get("ref") == schema["schema_ref"])
        else:
            schema = schema["schema"]
    return schema


def _patch_fields(schema: dict, definitions: list[dict], *, aliases: bool) -> dict:
    fields = {}
    for name, info in schema["fields"].items():
        options = {}
        if aliases and "validation_alias" in info:
            options["validation_alias"] = info["validation_alias"]
        fields[name] = core_schema.typed_dict_field(
            _patch_field_schema(info["schema"], definitions), required=False, **options)
    return core_schema.typed_dict_schema(fields,
        extra_behavior=schema.get("extra_behavior", "ignore"), config={"populate_by_name": True})


def _contains_patch_model(schema: dict) -> bool:
    if schema["type"] in ("model", "definition-ref"):
        return True
    if "schema" in schema:
        return _contains_patch_model(schema["schema"])
    if schema["type"] in ("union", "tagged-union"):
        choices = schema["choices"]
        return any(_contains_patch_model(c[0] if isinstance(c, tuple) else c)
                   for c in (choices.values() if isinstance(choices, dict) else choices))
    return False


def _patch_field_schema(schema: dict, definitions: list[dict]) -> dict:
    kind = schema["type"]
    if kind == "default":
        return _patch_field_schema(schema["schema"], definitions)
    if kind == "model" and not schema.get("root_model"):
        fields = dict(_model_fields_schema(schema, definitions))
        fields["extra_behavior"] = schema.get("config", {}).get("extra_fields_behavior", "ignore")
        return _patch_fields(fields, definitions, aliases=True)
    if kind == "definition-ref":
        target = next(item for item in definitions if item.get("ref") == schema["schema_ref"])
        return _patch_field_schema(target, definitions)
    if kind in ("nullable", "function-before"):
        return {**schema, "schema": _patch_field_schema(schema["schema"], definitions)}
    if kind in ("function-after", "function-wrap") and _contains_patch_model(schema):
        # These validators consume complete POJOs; run them after merge.
        return _patch_field_schema(schema["schema"], definitions)
    if kind == "tagged-union" and _contains_patch_model(schema):
        patched = {**schema, "choices": {k: _patch_field_schema(v, definitions)
                                        for k, v in schema["choices"].items()}}
        discriminator = schema["discriminator"]
        def validate(value, handler):
            if isinstance(value, dict) and isinstance(discriminator, str) and discriminator not in value:
                # The existing object's tag is available only after merge. Keep
                # every authored key, then validate against that selected branch.
                return dict(value)
            return handler(value)
        return core_schema.no_info_wrap_validator_function(validate, patched)
    if kind == "union" and _contains_patch_model(schema):
        def validate(value, handler):
            if isinstance(value, dict):
                return dict(value)  # branch selection belongs to merged validation
            return handler(value)
        return core_schema.no_info_wrap_validator_function(validate, schema)
    # Collections contain complete rows, so retain their full original schemas.
    return schema


@lru_cache
def _patch_validator(model_cls: type[BaseModel]) -> SchemaValidator:
    """Validate supplied fields; union patches without tags await merged validation.

    Before field validators are retained. Validators consuming complete nested
    POJOs and model invariants run on the full merged object, without patch defaults.
    """
    schema = model_cls.__pydantic_core_schema__
    definitions = schema.get("definitions", []) if schema["type"] == "definitions" else []
    fields = dict(_model_fields_schema(schema, definitions))
    fields["extra_behavior"] = model_cls.model_config.get("extra", "ignore")
    patch_schema = _patch_fields(fields, definitions, aliases=False)
    if definitions:
        patch_schema = core_schema.definitions_schema(patch_schema, definitions)
    return SchemaValidator(patch_schema)


def _reference_issues(value: Any, ctx: ResolveContext, references: WorldRegistryIndex) -> list[FieldPathError]:
    """Membership over validated POJOs, reusing nominal RegistryKey metadata."""
    issues = []
    if isinstance(value, BaseModel):
        for name, info in type(value).model_fields.items():
            item = getattr(value, name)
            child = ctx.child(name)
            target = registry_key_target(info.annotation)
            if target is not None and item is not None:
                keys = references.keys_for_registry(target)
                tokens = list(enumerate(item)) if isinstance(item, list) else [(None, item)]
                for index, token in tokens:
                    if keys is None or str(token) not in keys:
                        path = child.path_prefix if index is None else child.path_prefix + (index,)
                        issues.append(_validation_issue(child, path,
                            "reference index unavailable" if keys is None else f"unknown reference: {token!r}",
                            code="REF_W_UNAVAILABLE" if keys is None else "REF_W_UNKNOWN"))
            else:
                issues.extend(_reference_issues(item, child, references))
    elif isinstance(value, (list, dict)):
        for index, item in (enumerate(value) if isinstance(value, list) else value.items()):
            issues.extend(_reference_issues(item, ctx.child(index), references))
    return issues


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


def resolve_patch(model_cls: type[BaseModel], raw: dict[str, Any], *, ctx: ResolveContext) -> dict[str, Any]:
    """Validate supplied fields only; a patch is deliberately not a full POJO."""
    if not isinstance(raw, dict):
        reject_unresolved(ctx, [_validation_issue(ctx, ctx.path_prefix, "expected object", code="EXPECTED_OBJECT")])
    supplied = {}
    for name, info in model_cls.model_fields.items():
        value, present = _read_wire_field(raw, name, info)
        if present:
            supplied[name] = value
    known_keys = {key for name, info in model_cls.model_fields.items()
                  for key in _wire_lookup_keys(name, info)}
    supplied.update({key: value for key, value in raw.items() if key not in known_keys})
    try:
        payload = _patch_validator(model_cls).validate_python(supplied)
    except ValidationError as exc:
        reject_unresolved(ctx, [_validation_issue(ctx, ctx.path_prefix + tuple(e["loc"]),
            ("unknown wire value; " if e["type"] == "enum" else "") + e["msg"],
            code="UNKNOWN_ENUM" if e["type"] == "enum" else e["type"])
            for e in exc.errors()])
    return payload


def _wire_snapshot(raw: Any) -> Any:
    if isinstance(raw, dict):
        return copy.deepcopy(raw)
    return raw


def _resolved_snapshot(model: BaseModel) -> Any:
    return model.model_dump(mode="json")


def _json_line(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)



def _log_resolve_transform(
    label: str,
    wire: Any,
    result: BaseModel,
    ctx: ResolveContext | None,
) -> None:
    """Log original wire JSON vs resolved POJO when they differ."""
    before = _wire_snapshot(wire if isinstance(wire, dict) else {})
    after = _resolved_snapshot(result)
    before_json = _json_line(before)
    after_json = _json_line(after)
    if before_json == after_json:
        return
    mode = ctx.mode.value if ctx is not None else ResolveMode.RUNTIME.value
    logger.info(
        "json_validation | resolve | label=%s mode=%s | wire=%s | resolved=%s",
        label,
        mode,
        before_json,
        after_json,
    )


def _validation_issue(
    ctx: ResolveContext | None,
    path: tuple[str | int, ...],
    message: str,
    *,
    code: str,
) -> FieldPathError:
    return FieldPathError(
        path=path,
        message=message,
        schema_id=ctx.schema_id if ctx is not None else None,
        code=code,
    )


def _wire_lookup_keys(field_name: str, field_info: Any) -> tuple[str, ...]:
    """Python field name plus Pydantic validation / serialization aliases."""
    keys: list[str] = [field_name]
    alias = getattr(field_info, "alias", None)
    if isinstance(alias, str) and alias not in keys:
        keys.append(alias)
    validation_alias = getattr(field_info, "validation_alias", None)
    if isinstance(validation_alias, str):
        if validation_alias not in keys:
            keys.append(validation_alias)
    elif validation_alias is not None:
        choices = getattr(validation_alias, "choices", None)
        if choices:
            for choice in choices:
                if isinstance(choice, str) and choice not in keys:
                    keys.append(choice)
    return tuple(keys)


def _read_wire_field(
    raw: dict[str, Any],
    field_name: str,
    field_info: Any,
) -> tuple[Any, bool]:
    for key in _wire_lookup_keys(field_name, field_info):
        if key in raw:
            return raw[key], True
    return None, False


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
        path_prefix=(label,) if label else (), schema_id=getattr(model_cls, "SCHEMA_ID", None))
    if active_ctx.partial:
        raise TypeError("partial input is a patch; use resolve_patch and validate the merged object")
    try:
        result = model_cls.model_validate(raw, by_name=True, context=validation_context)
    except ValidationError as exc:
        reject_unresolved(active_ctx, [_validation_issue(active_ctx,
            active_ctx.path_prefix + tuple(part for part in e["loc"]
                if not isinstance(part, str) or not part.startswith(("is-instance[", "function-"))),
            ("unknown wire value; " if e["type"] == "enum" else "") + e["msg"],
            code="UNKNOWN_ENUM" if e["type"] == "enum" else e["type"])
            for e in exc.errors()])
    _log_resolve_transform(label or model_cls.__name__, raw, result, active_ctx)
    return result


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
        path_prefix=("worlds", world_uid, label) if world_uid else (label,),
        schema_id=getattr(registry_cls, "SCHEMA_ID", None))
    if raw is None or (isinstance(raw, list) and not raw):
        return empty_factory()
    active_ctx = ResolveContext(mode=active_ctx.mode, partial=False,
        path_prefix=active_ctx.path_prefix, report=active_ctx.report,
        schema_id=active_ctx.schema_id, validate_only=active_ctx.validate_only)
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
        path_prefix=("worlds", world_uid, label) if world_uid else (label,),
        schema_id=getattr(registry_cls, "SCHEMA_ID", None))
    if raw is None or (isinstance(raw, dict) and not raw):
        return empty_factory()
    active_ctx = ResolveContext(mode=active_ctx.mode, partial=False,
        path_prefix=active_ctx.path_prefix, report=active_ctx.report,
        schema_id=active_ctx.schema_id, validate_only=active_ctx.validate_only)
    return resolve_model(registry_cls, raw, label=label, ctx=active_ctx)
