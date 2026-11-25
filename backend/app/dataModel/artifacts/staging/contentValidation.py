"""Validate an existing content graph without replacing admitted instances."""

from dataclasses import fields, is_dataclass
from copy import deepcopy

from pydantic import BaseModel, RootModel

from app.dataModel.validation.immutableValue import validate_immutable


def _unchanged(original: object, checked: object) -> bool:
    if type(original) is not type(checked):
        return False
    if isinstance(original, BaseModel) and isinstance(checked, BaseModel):
        return (vars(original).keys() == vars(checked).keys()
                and all(_unchanged(value, vars(checked)[name]) for name, value in vars(original).items())
                and original.__pydantic_private__ == checked.__pydantic_private__)
    if isinstance(original, tuple) and isinstance(checked, tuple):
        return len(original) == len(checked) and all(_unchanged(a, b) for a, b in zip(original, checked))
    if isinstance(original, frozenset) and isinstance(checked, frozenset):
        return len(original) == len(checked) and all(
            any(_unchanged(a, b) for b in checked) for a in original)
    return original == checked


def require_unchanged_content(original: object, checked: object) -> None:
    if not _unchanged(original, checked):
        raise ValueError("artifact content must already satisfy its canonical schema")


def validate_content_instance(value: bytes | BaseModel) -> None:
    """Reject mutable, invalid or normalizing graphs, including trusted nested models."""
    validate_immutable(value)
    pending: list[object] = [value]
    seen: set[int] = set()
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        if isinstance(item, BaseModel):
            # Validators receive a temporary validation graph, never caller-owned
            # nested instances. The admitted/returned payload is not replaced.
            shadow = deepcopy(item)
            source = shadow.root if isinstance(shadow, RootModel) else dict(vars(shadow))
            checked = type(item).model_validate(source, strict=True, by_name=True)
            validate_immutable(checked)
            require_unchanged_content(item, checked)
            pending.extend(vars(item).values())
            pending.extend((item.__pydantic_private__ or {}).values())
        elif isinstance(item, (tuple, frozenset)):
            pending.extend(item)
        elif is_dataclass(item) and not isinstance(item, type):
            pending.extend(getattr(item, field.name) for field in fields(item))
