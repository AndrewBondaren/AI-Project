"""Shared multi_column scalar wire helpers for ``worlds`` row POJOs.

Climate / terrain / relief-obstacle (and future scalar slices) use the same
projection + startup column check — do not copy ``WIRE_KEYS`` /
``wire_from_mapping`` / ``validate_world_row_*`` per domain.

See ``docs/tz_generator_technical_debt.md`` **JV-SCALARS-1**.
"""

from __future__ import annotations

from dataclasses import fields as dataclass_fields
from typing import Any

from pydantic import BaseModel


def pojo_wire_keys(pojo_cls: type[BaseModel]) -> frozenset[str]:
    """Wire keys = POJO ``model_fields`` (single SoT for column names)."""
    return frozenset(pojo_cls.model_fields.keys())


def scalar_wire_from_mapping(
    keys: frozenset[str],
    source: Any,
) -> dict[str, Any]:
    """Project ``worlds`` row or wire dict → slice for ``resolve_model``."""
    if isinstance(source, dict):
        return {key: source.get(key) for key in keys}
    return {key: getattr(source, key, None) for key in keys}


def scalar_wire_from_pojo(
    pojo_cls: type[BaseModel],
    source: Any,
) -> dict[str, Any]:
    return scalar_wire_from_mapping(pojo_wire_keys(pojo_cls), source)


def validate_world_row_pojo_columns(
    world_cls: type,
    pojo_cls: type[BaseModel],
    *,
    label: str | None = None,
) -> None:
    """Startup assert: every POJO scalar field has a matching ``World`` column."""
    keys = pojo_wire_keys(pojo_cls)
    row_fields = {field.name for field in dataclass_fields(world_cls)}
    missing = keys - row_fields
    if missing:
        pojo_name = label or pojo_cls.__name__
        raise RuntimeError(
            f"{world_cls.__name__} missing {pojo_name} scalar columns "
            f"{sorted(missing)} — sync with {pojo_cls.__name__}",
        )
