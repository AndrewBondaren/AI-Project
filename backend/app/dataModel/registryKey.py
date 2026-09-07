"""Nominal N1-W registry key — JSON string branded by the registry POJO class.

Not ENUM-E: the world may add ranks. Type checkers distinguish
``RegistryKey[WorldSettlementSizeRegistry]`` from a bare ``str`` and from
``RegistryKey[OtherRegistry]``. Membership in the world's list is REF-W / ``entry_for``.

SoT: ``docs/tz_json_validation.md`` §0 RegistryKey.
"""

from __future__ import annotations

from types import UnionType
from typing import Any, Union, get_args, get_origin

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

from app.dataModel.annotationPolicy import unwrap_wire_type


class RegistryKey[R](str):
    """Identity string of N1-W registry ``R``. Wire remains a JSON string."""

    __slots__ = ()

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        origin = get_origin(source_type) or source_type
        key_cls: type[str] = origin if isinstance(origin, type) else cls

        def _to_key(value: str) -> str:
            return key_cls(value)

        from_str = core_schema.no_info_after_validator_function(
            _to_key,
            core_schema.str_schema(min_length=1),
        )
        return core_schema.json_or_python_schema(
            json_schema=from_str,
            python_schema=core_schema.union_schema([
                core_schema.is_instance_schema(key_cls),
                from_str,
            ]),
            serialization=core_schema.plain_serializer_function_ser_schema(
                str, when_used="json",
            ),
        )


def _peel_aliases(annotation: Any) -> Any:
    """Follow PEP 695 aliases and ``T | None`` so ``SettlementSizeKey`` resolves to ``R``."""
    inner = annotation
    while True:
        if type(inner).__name__ == "TypeAliasType":
            inner = inner.__value__
            continue
        origin = get_origin(inner)
        if origin is Union or origin is UnionType:
            args = [a for a in get_args(inner) if a is not type(None)]
            if len(args) == 1:
                inner = args[0]
                continue
        break
    return inner


def registry_key_target(annotation: Any) -> Any | None:
    """Return registry class ``R`` from ``RegistryKey[R]`` (after wire-policy unwrap)."""
    inner = _peel_aliases(unwrap_wire_type(annotation))
    origin = get_origin(inner)
    if origin is RegistryKey:
        args = get_args(inner)
        return args[0] if args else None
    return None
