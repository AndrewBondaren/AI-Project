"""Complete immutable-value validation shared by cascade, planning and cache."""

from dataclasses import fields, is_dataclass
from enum import Enum
from math import isfinite

from pydantic import BaseModel


def _complete_record(value: BaseModel) -> None:
    """Instance revalidation alone may silently restore missing default fields."""
    if set(vars(value)) != set(type(value).model_fields) or value.model_extra:
        raise ValueError("missing or extra record fields")


def _immutable(value: object, active: set[int]) -> None:
    """Reject shared mutable state, opaque live objects and cyclic graphs."""
    if value is None or isinstance(value, (str, bytes, bool, int)):
        return
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("non-finite cached number")
        return
    if isinstance(value, Enum):
        _immutable(value.value, active)
        return
    identity = id(value)
    if identity in active:
        raise ValueError("cyclic cached payload")
    active.add(identity)
    try:
        if isinstance(value, (tuple, frozenset)):
            for child in value:
                _immutable(child, active)
        elif isinstance(value, BaseModel):
            if not type(value).model_config.get("frozen"):
                raise ValueError("mutable cached model")
            _complete_record(value)
            for name in type(value).model_fields:
                _immutable(getattr(value, name), active)
            for child in (value.__pydantic_private__ or {}).values():
                _immutable(child, active)
        elif is_dataclass(value) and not isinstance(value, type):
            if not getattr(type(value), "__dataclass_params__").frozen:
                raise ValueError("mutable cached dataclass")
            if hasattr(value, "__dict__") and set(vars(value)) != {field.name for field in fields(value)}:
                raise ValueError("missing or extra dataclass fields")
            for field in fields(value):
                _immutable(getattr(value, field.name), active)
        else:
            raise ValueError("unsupported or mutable cached value")
    finally:
        active.remove(identity)


def validate_immutable(value: object) -> None:
    """Public admission check for complete, immutable records and nested values."""
    _immutable(value, set())
