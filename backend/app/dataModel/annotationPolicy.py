"""Per-field import wire policy for master-data POJOs — ``docs/tz_json_validation.md``."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, get_args, get_origin

_WIRE_ALIAS_NAMES = frozenset({
    "StrictOnWire",
    "IgnoreOnWire",
    "DefaultOnWire",
    "StrictEnumOnWire",
    "DefaultEnumOnWire",
})


class WireFieldPolicy(StrEnum):
    """Per-field import policy (explicit on every wire-backed field)."""

    STRICT_ON_WIRE = "strict_on_wire"
    """Missing or invalid wire → reject on import / warn on runtime."""

    IGNORE_ON_WIRE = "ignore_on_wire"
    """Wire only when present — no ``Field`` default fill."""

    DEFAULT = "default"
    """Missing or invalid wire → ``Field`` default + log."""


class EnumWire:
    """Marker: wire value must be a member of annotated ``StrEnum`` (``parse_enum``)."""


type StrictOnWire[T] = Annotated[T, WireFieldPolicy.STRICT_ON_WIRE]
type IgnoreOnWire[T] = Annotated[T, WireFieldPolicy.IGNORE_ON_WIRE]
type DefaultOnWire[T] = Annotated[T, WireFieldPolicy.DEFAULT]

type StrictEnumOnWire[E: StrEnum] = Annotated[
    E,
    WireFieldPolicy.STRICT_ON_WIRE,
    EnumWire(),
]
type DefaultEnumOnWire[E: StrEnum] = Annotated[
    E,
    WireFieldPolicy.DEFAULT,
    EnumWire(),
]


def _annotation_parts(annotation: Any) -> tuple[Any, tuple[Any, ...]]:
    """Unwrap PEP 695 wire aliases; return inner type and collected metadata."""
    if hasattr(annotation, "__value__"):
        annotation = annotation.__value__

    meta: list[Any] = []
    inner = annotation
    while True:
        if get_origin(inner) is Annotated:
            args = get_args(inner)
            if not args:
                break
            inner = args[0]
            meta.extend(args[1:])
            continue
        origin = get_origin(inner)
        if origin is not None and getattr(origin, "__name__", "") in _WIRE_ALIAS_NAMES:
            args = get_args(inner)
            if not args:
                break
            inner = args[0]
            continue
        break
    return inner, tuple(meta)


def unwrap_wire_type(annotation: Any) -> Any:
    """Inner field type after stripping wire policy / enum aliases."""
    inner, _meta = _annotation_parts(annotation)
    return inner


def field_policy(annotation: Any) -> WireFieldPolicy:
    """Extract per-field wire policy; unannotated fields → ``DEFAULT``."""
    _inner, meta = _annotation_parts(annotation)
    for item in meta:
        if isinstance(item, WireFieldPolicy):
            return item
    return WireFieldPolicy.DEFAULT


def wire_enum_class(annotation: Any) -> type[StrEnum] | None:
    """Return ``StrEnum`` class when field carries ``EnumWire`` marker."""
    _inner, meta = _annotation_parts(annotation)
    if not any(isinstance(item, EnumWire) for item in meta):
        return None

    outer_args = get_args(annotation)
    if outer_args:
        candidate = outer_args[0]
        if isinstance(candidate, type) and issubclass(candidate, StrEnum):
            return candidate

    inner = unwrap_wire_type(annotation)
    if isinstance(inner, type) and issubclass(inner, StrEnum):
        return inner
    return None
