"""POJO resolve/normalize — single engine for import validator and runtime reads.

Field policy: ``WireFieldPolicy`` — ``StrictOnWire`` / ``IgnoreOnWire`` / ``DefaultOnWire``.
Contract: ``docs/tz_json_validation.md``.
"""

from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Annotated, Any, get_args, get_origin

from pydantic import BaseModel, RootModel, TypeAdapter, ValidationError
from pydantic_core import PydanticUndefined

from app.dataModel.annotationPolicy import (
    WireFieldPolicy,
    field_policy,
    unwrap_wire_type,
    wire_enum_class,
)
from app.application.jsonValidation.types import FieldPathError
from app.application.jsonValidation.wire import WireEnumError, parse_enum

logger = logging.getLogger(__name__)


class ResolveMode(StrEnum):
    RUNTIME = "runtime"
    IMPORT = "import"


@dataclass
class ResolveContext:
    mode: ResolveMode = ResolveMode.RUNTIME
    partial: bool = False
    path_prefix: tuple[str | int, ...] = ()
    errors: list[FieldPathError] = field(default_factory=list)
    schema_id: str | None = None

    def child(self, segment: str | int) -> ResolveContext:
        return ResolveContext(
            mode=self.mode,
            partial=self.partial,
            path_prefix=self.path_prefix + (segment,),
            errors=self.errors,
            schema_id=self.schema_id,
        )


class StrictFieldError(ValueError):
    def __init__(self, path: tuple[str | int, ...], detail: str) -> None:
        self.path = path
        self.detail = detail
        super().__init__(
            f"{'.'.join(str(part) for part in path)}: {detail}" if path else detail,
        )


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
    if not isinstance(raw, dict):
        raw = {}

    payload: dict[str, Any] = {}
    for name, field_info in model_cls.model_fields.items():
        raw_value, present = _read_wire_field(raw, name, field_info)
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

    if ctx is not None and ctx.mode == ResolveMode.IMPORT and ctx.errors:
        result = model_cls.model_construct(**payload)
        _log_resolve_transform(label or model_cls.__name__, raw, result, ctx)
        return result

    try:
        result = model_cls.model_validate(payload)
        _log_resolve_transform(label or model_cls.__name__, raw, result, ctx)
        return result
    except ValidationError as exc:
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
        except StrictFieldError as exc:
            logger.warning(
                "json_validation | %s strict field failed (%s); field omitted",
                label,
                exc,
            )
    return model_cls.model_construct(**payload)


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
    for index, item in enumerate(raw):
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
        before_errors = len(ctx.errors) if ctx is not None else 0
        entries.append(
            resolve_model(entry_cls, item, label=f"{label}[{index}]", ctx=row_ctx),
        )
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
