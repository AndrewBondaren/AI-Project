"""POJO resolve/normalize — single engine for import validator and runtime reads.

Field policy: ``WireFieldPolicy`` — ``StrictOnWire`` / ``IgnoreOnWire`` /
``DefaultOnWire`` (legacy) / ``DefaultWhenMissing``.
Contract: ``docs/tz_json_validation.md``.
"""

from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Annotated, Any, NoReturn, TYPE_CHECKING, get_args, get_origin

from pydantic import BaseModel, RootModel, TypeAdapter, ValidationError
from pydantic_core import PydanticUndefined

from app.dataModel.annotationPolicy import (
    WireFieldPolicy,
    field_policy,
    unwrap_wire_type,
    wire_enum_class,
)
from app.application.jsonValidation.types import FieldPathError, ResolveReport
from app.application.jsonValidation.wire import WireEnumError, parse_enum
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


def _field_adapter(field_info: Any) -> TypeAdapter:
    # Reuse Pydantic's Field constraints (ge, length, validators, etc.).
    annotation = field_info.annotation
    if field_info.metadata:
        annotation = Annotated[annotation, *field_info.metadata]
    return TypeAdapter(annotation)


def _has_missing_contract(annotation: Any, seen: frozenset[int] = frozenset()) -> bool:
    if id(annotation) in seen:
        return False
    seen = seen | {id(annotation)}
    if field_policy(annotation) == WireFieldPolicy.DEFAULT_WHEN_MISSING:
        return True
    inner = unwrap_wire_type(annotation)
    if isinstance(inner, type) and issubclass(inner, BaseModel):
        return any(_has_missing_contract(info.annotation, seen) for info in inner.model_fields.values())
    return any(_has_missing_contract(arg, seen) for arg in get_args(inner))


def _contract_issues(
    annotation: Any, raw: Any, ctx: ResolveContext,
    references: WorldRegistryIndex | None,
) -> list[FieldPathError]:
    """Inspect new contracts before any legacy parent can repair invalid input.

    This is the same field engine's preflight, including nested collections;
    old wire policies keep their explicitly unmigrated behavior.
    """
    inner = unwrap_wire_type(annotation)
    origin = get_origin(inner)
    if origin is Annotated:
        return _contract_issues(get_args(inner)[0], raw, ctx, references)
    if isinstance(inner, type) and issubclass(inner, BaseModel):
        if issubclass(inner, RootModel):
            return _contract_issues(inner.model_fields["root"].annotation, raw, ctx, references)
        if not isinstance(raw, dict):
            return ([_validation_issue(ctx, ctx.path_prefix, "expected object", code="EXPECTED_OBJECT")]
                    if _has_missing_contract(inner) else [])
        issues: list[FieldPathError] = []
        for name, info in inner.model_fields.items():
            value, present = _read_wire_field(raw, name, info)
            child = ctx.child(name)
            if field_policy(info.annotation) == WireFieldPolicy.DEFAULT_WHEN_MISSING:
                if not present and ctx.partial:
                    continue
                if not present:
                    value = _field_default(info)
                    if value is PydanticUndefined:
                        issues.append(_validation_issue(child, child.path_prefix, "field required", code="missing"))
                        continue
                try:
                    value = _field_adapter(info).validate_python(value)
                except ValidationError as exc:
                    target = registry_key_target(info.annotation)
                    issues.extend(_validation_issue(child, child.path_prefix + tuple(
                                  part for part in e["loc"] if target is None or isinstance(part, int)),
                                  e["msg"], code=e["type"]) for e in exc.errors())
                    continue
                target = registry_key_target(info.annotation)
                if value is not None and target is not None and references is not None:
                    keys = references.keys_for_registry(target)
                    values = list(enumerate(value)) if isinstance(value, list) else [(None, value)]
                    for index, token in values:
                        if keys is None or str(token) not in keys:
                            path = child.path_prefix if index is None else child.path_prefix + (index,)
                            issues.append(_validation_issue(child, path,
                                "reference index unavailable" if keys is None else f"unknown reference: {token!r}",
                                code="REF_W_UNAVAILABLE" if keys is None else "REF_W_UNKNOWN"))
            if present and value is not None:
                issues.extend(_contract_issues(info.annotation, value, child, references))
        return issues
    if origin is list and isinstance(raw, list):
        return [issue for i, item in enumerate(raw)
                for issue in _contract_issues(get_args(inner)[0], item, ctx.child(i), references)]
    if origin is dict and isinstance(raw, dict):
        return [issue for key, item in raw.items()
                for issue in _contract_issues(get_args(inner)[1], item, ctx.child(key), references)]
    if origin in (list, dict) and _has_missing_contract(inner):
        return [_validation_issue(ctx, ctx.path_prefix, f"expected {origin.__name__}",
                                  code="EXPECTED_LIST" if origin is list else "EXPECTED_OBJECT")]
    # Optional model and PEP 695 domain aliases, without reinterpreting null.
    if type(inner).__name__ == "TypeAliasType":
        return _contract_issues(inner.__value__, raw, ctx, references)
    if raw is not None:
        for arg in get_args(inner):
            if arg is not type(None):
                found = _contract_issues(arg, raw, ctx, references)
                if found:
                    return found
    return []


def validate_contracts(model_cls: type[BaseModel], raw: Any, *, ctx: ResolveContext,
                       references: WorldRegistryIndex | None = None) -> None:
    issues = _contract_issues(model_cls, raw, ctx, references)
    if issues:
        reject_unresolved(ctx, issues)


def resolve_result(model_cls: type[BaseModel], raw: Any, *, ctx: ResolveContext | None = None,
                   references: WorldRegistryIndex | None = None) -> ResolveResult:
    ctx = ctx if ctx is not None else ResolveContext()
    before = len(ctx.errors)
    try:
        validate_contracts(model_cls, raw, ctx=ctx, references=references)
        value = resolve_model(model_cls, raw, ctx=ctx)
        if len(ctx.errors) > before:
            return ResolveResult(None, tuple(ctx.errors[before:]))
        # Legacy resolve_model may construct an unchecked object. The typed
        # result boundary never advertises such a value as a resolved POJO.
        if not _has_missing_contract(model_cls):
            try:
                value = model_cls.model_validate(value.model_dump(exclude_unset=True), by_name=True)
            except ValidationError as exc:
                reject_unresolved(ctx, [_validation_issue(ctx, ctx.path_prefix + tuple(e["loc"]),
                                  e["msg"], code=e["type"]) for e in exc.errors()])
        return ResolveResult(value)
    except UnresolvedModelError as exc:
        return ResolveResult(None, tuple(exc.issues))


def resolve_patch(model_cls: type[BaseModel], raw: dict[str, Any], *, ctx: ResolveContext) -> dict[str, Any]:
    """Validate supplied fields only; a patch is deliberately not a full POJO."""
    validate_contracts(model_cls, raw, ctx=ctx)
    payload: dict[str, Any] = {}
    for name, info in model_cls.model_fields.items():
        value, present = _read_wire_field(raw, name, info)
        if not present:
            continue
        inner = unwrap_wire_type(info.annotation)
        if _is_base_model_type(info.annotation) and isinstance(value, dict):
            payload[name] = resolve_patch(inner, value, ctx=ctx.child(name))
        else:
            resolved = _resolve_field(info, value, field_name=name, label=model_cls.__name__, present=True, ctx=ctx)
            if resolved is not PydanticUndefined:
                payload[name] = resolved.model_dump(mode="json") if isinstance(resolved, BaseModel) else resolved
    return payload


def _unwrap_annotation(annotation: Any) -> Any:
    return unwrap_wire_type(annotation)


def _field_default(field_info: Any) -> Any:
    if field_info.default_factory is not None:
        return field_info.default_factory()
    if field_info.default is not PydanticUndefined:
        return field_info.default
    return PydanticUndefined


def _is_base_model_type(annotation: Any) -> bool:
    inner = _unwrap_annotation(annotation)
    return isinstance(inner, type) and issubclass(inner, BaseModel)


def _validation_message(exc: ValidationError) -> str:
    parts: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"])
        parts.append(f"{loc}: {err['msg']}")
    return "; ".join(parts)


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


def _wire_str(raw_value: Any) -> str:
    return raw_value if isinstance(raw_value, str) else str(raw_value)


def _resolve_str_enum(
    enum_cls: type[StrEnum],
    raw_value: Any,
    *,
    field_name: str,
    field_path: tuple[str | int, ...],
    ctx: ResolveContext | None,
) -> Any:
    """Parse ENUM-E wire on import (UNKNOWN_ENUM 422) or runtime (caller handles fallback)."""
    if isinstance(raw_value, enum_cls):
        return raw_value

    try:
        return parse_enum(enum_cls, _wire_str(raw_value), field=field_name)
    except WireEnumError as exc:
        if ctx is not None and ctx.mode == ResolveMode.IMPORT:
            ctx.errors.append(_validation_issue(
                ctx,
                field_path,
                str(exc),
                code="UNKNOWN_ENUM",
            ))
            return PydanticUndefined
        raise StrictFieldError(field_path, str(exc)) from exc


def _record_strict_error(
    ctx: ResolveContext | None,
    path: tuple[str | int, ...],
    detail: str,
) -> None:
    if ctx is not None and ctx.mode == ResolveMode.IMPORT:
        ctx.errors.append(_validation_issue(ctx, path, detail, code="STRICT_REQUIRED"))
        return
    raise StrictFieldError(path, detail)


def _resolve_field(
    field_info: Any,
    raw_value: Any,
    *,
    field_name: str,
    label: str,
    present: bool,
    ctx: ResolveContext | None = None,
) -> Any:
    policy = field_policy(field_info.annotation)
    inner = _unwrap_annotation(field_info.annotation)
    field_path = (ctx.path_prefix + (field_name,)) if ctx is not None else (field_name,)

    if ctx is not None and ctx.partial and not present:
        return PydanticUndefined

    if policy == WireFieldPolicy.DEFAULT_WHEN_MISSING:
        value = raw_value if present else _field_default(field_info)
        try:
            return _field_adapter(field_info).validate_python(value)
        except ValidationError as exc:
            active_ctx = ctx if ctx is not None else ResolveContext()
            reject_unresolved(active_ctx, [_validation_issue(active_ctx, field_path + tuple(e["loc"]),
                              e["msg"], code=e["type"]) for e in exc.errors()])

    if policy == WireFieldPolicy.IGNORE_ON_WIRE:
        if not present:
            return PydanticUndefined
        if isinstance(raw_value, dict) and _is_base_model_type(field_info.annotation):
            child = ctx.child(field_name) if ctx is not None else None
            return resolve_model(inner, raw_value, label=f"{label}.{field_name}", ctx=child)
        return raw_value

    if policy == WireFieldPolicy.STRICT_ON_WIRE:
        if not present or raw_value is None:
            if field_info.is_required():
                _record_strict_error(ctx, field_path, "strict field is required")
                return PydanticUndefined
            return None
        if isinstance(raw_value, dict) and _is_base_model_type(field_info.annotation):
            child = ctx.child(field_name) if ctx is not None else None
            return resolve_model(inner, raw_value, label=f"{label}.{field_name}", ctx=child)
        enum_cls = wire_enum_class(field_info.annotation)
        if enum_cls is not None:
            try:
                return _resolve_str_enum(
                    enum_cls,
                    raw_value,
                    field_name=field_name,
                    field_path=field_path,
                    ctx=ctx,
                )
            except StrictFieldError as exc:
                _record_strict_error(ctx, exc.path, exc.detail)
                return PydanticUndefined
        try:
            TypeAdapter(inner).validate_python(raw_value)
        except ValidationError as exc:
            _record_strict_error(ctx, field_path, _validation_message(exc))
            return PydanticUndefined
        return raw_value

    if present and raw_value is not None:
        if isinstance(raw_value, dict) and _is_base_model_type(field_info.annotation):
            child = ctx.child(field_name) if ctx is not None else None
            return resolve_model(inner, raw_value, label=f"{label}.{field_name}", ctx=child)
        enum_cls = wire_enum_class(field_info.annotation)
        if enum_cls is not None:
            try:
                return _resolve_str_enum(
                    enum_cls,
                    raw_value,
                    field_name=field_name,
                    field_path=field_path,
                    ctx=ctx,
                )
            except StrictFieldError:
                logger.warning(
                    "json_validation | %s.%s invalid enum; using field default",
                    label,
                    field_name,
                )
        else:
            try:
                return TypeAdapter(inner).validate_python(raw_value)
            except ValidationError:
                logger.warning(
                    "json_validation | %s.%s invalid; using field default",
                    label,
                    field_name,
                )

    default = _field_default(field_info)
    if default is PydanticUndefined:
        return raw_value if present else PydanticUndefined
    if not present:
        logger.warning(
            "json_validation | %s.%s missing; using field default",
            label,
            field_name,
        )
    return default


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


def resolve_model(
    model_cls: type[BaseModel],
    raw: Any,
    *,
    label: str = "",
    ctx: ResolveContext | None = None,
) -> BaseModel:
    """Build POJO from wire dict using per-field annotation policy."""
    if ctx is not None and ctx.partial and _has_missing_contract(model_cls):
        raise TypeError("partial input is a patch; use resolve_patch and validate the merged object")
    validate_contracts(model_cls, raw, ctx=ctx if ctx is not None else ResolveContext())
    if not isinstance(raw, dict):
        raw = {}

    has_new_contract = _has_missing_contract(model_cls)
    payload: dict[str, Any] = {}
    for name, field_info in model_cls.model_fields.items():
        raw_value, present = _read_wire_field(raw, name, field_info)
        if has_new_contract and not present and not field_info.is_required():
            # Let Pydantic apply the declared default while preserving authored
            # field presence for model invariants (e.g. count vs count_range).
            continue
        value = _resolve_field(
            field_info,
            raw_value,
            field_name=name,
            label=label or model_cls.__name__,
            present=present,
            ctx=ctx,
        )
        if value is not PydanticUndefined:
            if value is None and not present:
                continue
            if value is None and present:
                default = _field_default(field_info)
                if default is None:
                    continue
            payload[name] = value

    if ctx is not None and ctx.mode == ResolveMode.IMPORT and ctx.errors and not has_new_contract:
        result = model_cls.model_construct(**payload)
        _log_resolve_transform(label or model_cls.__name__, raw, result, ctx)
        return result

    try:
        result = model_cls.model_validate(payload, by_name=True)
        _log_resolve_transform(label or model_cls.__name__, raw, result, ctx)
        return result
    except ValidationError as exc:
        if has_new_contract:
            active_ctx = ctx if ctx is not None else ResolveContext()
            reject_unresolved(active_ctx, [_validation_issue(active_ctx,
                active_ctx.path_prefix + tuple(e["loc"]), e["msg"], code=e["type"])
                for e in exc.errors()])
        # Cross-field POJO invariants cannot be repaired by constructing an
        # unchecked instance. Preserve import paths / runtime row rejection.
        model_errors = [error for error in exc.errors() if not error["loc"]]
        if model_errors:
            for error in model_errors:
                _record_strict_error(ctx, ctx.path_prefix if ctx is not None else (), error["msg"])
            return model_cls.model_construct(**payload)
        logger.warning(
            "json_validation | %s model_validate failed (%s issues); retry field-wise",
            label or model_cls.__name__,
            exc.error_count(),
        )
        result = _resolve_fieldwise(model_cls, raw, label=label or model_cls.__name__, ctx=ctx)
        _log_resolve_transform(label or model_cls.__name__, raw, result, ctx)
        return result


def _resolve_fieldwise(
    model_cls: type[BaseModel],
    raw: dict[str, Any],
    *,
    label: str,
    ctx: ResolveContext | None = None,
) -> BaseModel:
    payload: dict[str, Any] = {}
    for name, field_info in model_cls.model_fields.items():
        try:
            raw_value, present = _read_wire_field(raw, name, field_info)
            value = _resolve_field(
                field_info,
                raw_value,
                field_name=name,
                label=label,
                present=present,
                ctx=ctx,
            )
            if value is not PydanticUndefined:
                if value is None and name not in raw:
                    continue
                payload[name] = value
        except UnresolvedModelError:
            raise
        except StrictFieldError as exc:
            logger.warning(
                "json_validation | %s strict field failed (%s); field omitted",
                label,
                exc,
            )
    return model_cls.model_construct(**payload)


def _is_string_scalar_entry(entry_cls: Any) -> bool:
    """Root list of bare strings / ``RegistryKey`` (not a closed StrEnum)."""
    if entry_cls is str:
        return True
    if not isinstance(entry_cls, type):
        return False
    if issubclass(entry_cls, StrEnum):
        return False
    return issubclass(entry_cls, str)


def resolve_root_list(
    registry_cls: type[RootModel],
    raw: Any,
    *,
    empty_factory: Any,
    label: str,
    world_uid: str | None = None,
    ctx: ResolveContext | None = None,
) -> RootModel:
    """Parse ``RootModel[list[Entry]]`` — per-row resolve, no nuclear registry fallback."""
    if not raw:
        return empty_factory()

    if not isinstance(raw, list):
        if ctx is not None and ctx.mode == ResolveMode.IMPORT:
            ctx.errors.append(_validation_issue(
                ctx,
                ctx.path_prefix,
                "expected list",
                code="EXPECTED_LIST",
            ))
            return empty_factory()
        logger.warning(
            "json_validation | world=%s %s expected list; using empty defaults",
            world_uid or "?",
            label,
        )
        return empty_factory()

    root_field = registry_cls.model_fields.get("root")
    if root_field is None:
        return empty_factory()

    entry_cls = _unwrap_annotation(root_field.annotation)
    if get_origin(entry_cls) is list:
        args = get_args(entry_cls)
        entry_cls = args[0] if args else entry_cls

    entries: list[Any] = []
    enum_scalars = isinstance(entry_cls, type) and issubclass(entry_cls, StrEnum)
    string_scalars = _is_string_scalar_entry(entry_cls)
    for index, item in enumerate(raw):
        if enum_scalars and not isinstance(item, dict):
            member: Any = item if isinstance(item, entry_cls) else None
            if member is None:
                from_wire = getattr(entry_cls, "from_wire", None)
                if callable(from_wire):
                    member = from_wire(item)
            if member is None:
                logger.warning(
                    "json_validation | world=%s %s[%s] unknown enum %r; skipped",
                    world_uid or "?",
                    label,
                    index,
                    item,
                )
                continue
            entries.append(member)
            continue
        if string_scalars and not isinstance(item, dict):
            token = str(item).strip() if item is not None else ""
            if not token:
                continue
            entries.append(token if entry_cls is str else entry_cls(token))
            continue
        if not isinstance(item, dict):
            if ctx is not None and ctx.mode == ResolveMode.IMPORT:
                ctx.errors.append(_validation_issue(
                    ctx,
                    ctx.path_prefix + (index,),
                    "expected object",
                    code="EXPECTED_OBJECT",
                ))
            else:
                logger.warning(
                    "json_validation | world=%s %s[%s] not an object; skipped",
                    world_uid or "?",
                    label,
                    index,
                )
            continue

        row_ctx = ctx.child(index) if ctx is not None else None
        if row_ctx is not None:
            # A partial world write replaces a supplied registry collection;
            # each supplied row is complete, not a partial entry patch.
            row_ctx.partial = False
        before_errors = len(ctx.errors) if ctx is not None else 0
        try:
            entry = resolve_model(entry_cls, item, label=f"{label}[{index}]", ctx=row_ctx)
        except UnresolvedModelError:
            raise
        except StrictFieldError as exc:
            logger.warning(
                "json_validation | world=%s %s[%s] invalid row (%s); skipped",
                world_uid or "?", label, index, exc,
            )
            continue
        entries.append(entry)
        if ctx is not None and ctx.mode == ResolveMode.IMPORT and len(ctx.errors) > before_errors:
            entries.pop()

    if not entries:
        return empty_factory()

    return registry_cls(entries)


def resolve_root_dict(
    registry_cls: type[RootModel],
    raw: Any,
    *,
    empty_factory: Any,
    label: str,
    world_uid: str | None = None,
    ctx: ResolveContext | None = None,
) -> RootModel:
    """Parse ``RootModel[dict[str, Entry]]`` — per-key resolve, no nuclear registry fallback."""
    if not raw:
        return empty_factory()

    if not isinstance(raw, dict):
        if ctx is not None and ctx.mode == ResolveMode.IMPORT:
            ctx.errors.append(_validation_issue(
                ctx,
                ctx.path_prefix,
                "expected object",
                code="EXPECTED_OBJECT",
            ))
            return empty_factory()
        logger.warning(
            "json_validation | world=%s %s expected object; using empty defaults",
            world_uid or "?",
            label,
        )
        return empty_factory()

    root_field = registry_cls.model_fields.get("root")
    if root_field is None:
        return empty_factory()

    entry_cls = _unwrap_annotation(root_field.annotation)
    if get_origin(entry_cls) is dict:
        args = get_args(entry_cls)
        entry_cls = args[1] if len(args) > 1 else entry_cls

    entries: dict[str, Any] = {}
    for map_key, item in raw.items():
        if not isinstance(item, dict):
            if ctx is not None and ctx.mode == ResolveMode.IMPORT:
                ctx.errors.append(_validation_issue(
                    ctx,
                    ctx.path_prefix + (map_key,),
                    "expected object",
                    code="EXPECTED_OBJECT",
                ))
            else:
                logger.warning(
                    "json_validation | world=%s %s[%s] not an object; skipped",
                    world_uid or "?",
                    label,
                    map_key,
                )
            continue

        row_ctx = ctx.child(map_key) if ctx is not None else None
        before_errors = len(ctx.errors) if ctx is not None else 0
        entries[map_key] = resolve_model(
            entry_cls,
            item,
            label=f"{label}[{map_key}]",
            ctx=row_ctx,
        )
        if ctx is not None and ctx.mode == ResolveMode.IMPORT and len(ctx.errors) > before_errors:
            entries.pop(map_key, None)

    if not entries:
        return empty_factory()

    return registry_cls(entries)
