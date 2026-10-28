"""Presence-based wire migration; called by the owning POJO's before validator."""

# TODO: удалить этот legacy-модуль и вызовы normalizer после миграции старых
# JSON-настроек и завершения поддержки legacy-полей при импорте.

from pydantic import BaseModel, StrictBool, TypeAdapter
from pydantic_core import PydanticCustomError

_OLD_BOOL = TypeAdapter(StrictBool)
_NEW_BOOL = TypeAdapter(StrictBool | None)


def _wire_object(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{path} must be an object with string keys")
    return {key: item for key, item in value.items()}


def _migrate_flag(raw: dict[str, object], old: str, target: str) -> dict[str, object]:
    if old not in raw:
        return raw
    legacy = _OLD_BOOL.validate_python(raw[old], strict=True)
    child = raw.get(target, {})
    if isinstance(child, BaseModel):
        # Revalidate typed copies, and retain explicit None versus absent fields.
        child = type(child).model_validate(child, strict=True).model_dump(exclude_unset=True)
    nested = _wire_object(child, target)
    if "autoresolve" in nested:
        current = _NEW_BOOL.validate_python(nested["autoresolve"], strict=True)
        if current is not legacy:
            raise PydanticCustomError("GENERATION_SETTINGS_CONFLICT",
                "{legacy} conflicts with {target}.autoresolve", {"legacy": old, "target": target})
    else:
        nested["autoresolve"] = legacy
    result = dict(raw)
    result.pop(old)
    result[target] = nested
    return result


def normalize_seas_generation(value: object) -> object:
    if isinstance(value, BaseModel):
        return value
    raw = _wire_object(value, "default_seas")
    raw = _migrate_flag(raw, "autoresolve_coastal_sea", "sea_generation")
    return _migrate_flag(raw, "autoresolve_open_ocean", "ocean_generation")


def normalize_lakes_generation(value: object) -> object:
    if isinstance(value, BaseModel):
        return value
    return _migrate_flag(_wire_object(value, "default_lakes"), "autoresolve", "generation")
