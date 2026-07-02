"""Wire ↔ domain boundary helpers — ENUM-E parse at jsonValidation layer."""

from __future__ import annotations

from enum import StrEnum
from typing import TypeVar

E = TypeVar("E", bound=StrEnum)


class WireEnumError(ValueError):
    def __init__(self, field: str, wire: str, enum_cls: type[StrEnum]) -> None:
        self.field = field
        self.wire = wire
        self.enum_cls = enum_cls
        values = ", ".join(m.value for m in enum_cls)
        super().__init__(f"{field}: unknown wire value {wire!r}; expected one of: {values}")


def parse_enum(enum_cls: type[E], wire: str, *, field: str) -> E:
    try:
        return enum_cls(wire)
    except ValueError as exc:
        raise WireEnumError(field, wire, enum_cls) from exc
