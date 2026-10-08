"""Per-field import wire policy for master-data POJOs — ``docs/tz_json_validation.md``."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, get_args, get_origin

_WIRE_ALIAS_NAMES = frozenset({
    "StrictOnWire",
    "IgnoreOnWire",
    "DefaultOnWire",
    "DefaultWhenMissing",
    "StrictEnumOnWire",
    "DefaultEnumOnWire",
    "DefaultEnumWhenMissing",
})


class WireFieldPolicy(StrEnum):
    """Per-field import policy (explicit on every wire-backed field)."""

    STRICT_ON_WIRE = "strict_on_wire"
    """Missing or invalid wire → reject on import / warn on runtime."""

    IGNORE_ON_WIRE = "ignore_on_wire"
    """Wire only when present — no ``Field`` default fill."""

    DEFAULT = "default"
    """Deprecated metadata value; no error-default execution path remains."""

    DEFAULT_WHEN_MISSING = "default_when_missing"
    """Missing wire → schema default; supplied invalid value → unresolved."""


class EnumWire:
    """Closed StrEnum wire contract; invalid enum diagnostics use UNKNOWN_ENUM."""


type StrictOnWire[T] = Annotated[T, WireFieldPolicy.STRICT_ON_WIRE]
type IgnoreOnWire[T] = Annotated[T, WireFieldPolicy.IGNORE_ON_WIRE]
# Deprecated import names retain source compatibility, with the migrated policy.
type DefaultOnWire[T] = Annotated[T, WireFieldPolicy.DEFAULT_WHEN_MISSING]
type DefaultWhenMissing[T] = Annotated[T, WireFieldPolicy.DEFAULT_WHEN_MISSING]
type DefaultEnumWhenMissing[E] = Annotated[
    E, WireFieldPolicy.DEFAULT_WHEN_MISSING, EnumWire(),
]

type StrictEnumOnWire[E: StrEnum] = Annotated[
    E,
    WireFieldPolicy.STRICT_ON_WIRE,
    EnumWire(),
]
type DefaultEnumOnWire[E: StrEnum] = Annotated[
    E,
    WireFieldPolicy.DEFAULT_WHEN_MISSING,
    EnumWire(),
]


def _annotation_parts(annotation: Any) -> tuple[Any, tuple[Any, ...]]:
    """Unwrap PEP 695 wire aliases; return inner type and collected metadata.

    Specialized aliases (``StrictOnWire[Concrete]``) are ``GenericAlias``: do
    not peel ``__value__`` (that is ``Annotated[T, …]`` with the unbound TypeVar).
    Policy metadata comes from the alias origin's ``Annotated`` value.
    """
    meta: list[Any] = []
    inner = annotation
    while True:
        origin = get_origin(inner)
        if origin is not None and getattr(origin, "__name__", "") in _WIRE_ALIAS_NAMES:
            args = get_args(inner)
            alias_val = getattr(origin, "__value__", None)
            if get_origin(alias_val) is Annotated:
                meta.extend(get_args(alias_val)[1:])
            if not args:
                break
            inner = args[0]
            continue
        if type(inner).__name__ == "TypeAliasType":
            inner = inner.__value__
            continue
        if get_origin(inner) is Annotated:
            args = get_args(inner)
            if not args:
                break
            rest = args[1:]
            meta.extend(rest)
            # Wire aliases only. Keep Pydantic BeforeValidator / other constraints
            # so resolve TypeAdapter still coerces (POJO-C-9 sides).
            if rest and not all(
                isinstance(item, (WireFieldPolicy, EnumWire)) for item in rest
            ):
                nested, nested_meta = _annotation_parts(args[0])
                return Annotated[nested, *rest], tuple(meta) + nested_meta
            inner = args[0]
            continue
        break
    return inner, tuple(meta)


def unwrap_wire_type(annotation: Any) -> Any:
    """Inner field type after stripping wire policy / enum aliases."""
    inner, _meta = _annotation_parts(annotation)
    return inner


def field_policy(annotation: Any) -> WireFieldPolicy:
    """Extract policy; unannotated fields use the schema's missing contract."""
    _inner, meta = _annotation_parts(annotation)
    for item in meta:
        if isinstance(item, WireFieldPolicy):
            return item
    return WireFieldPolicy.DEFAULT_WHEN_MISSING


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
    for candidate in get_args(inner):
        if isinstance(candidate, type) and issubclass(candidate, StrEnum):
            return candidate
    return None
