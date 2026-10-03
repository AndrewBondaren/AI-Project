"""Wire district boundary entry node roles — settlement → district road planning."""

from __future__ import annotations

from enum import StrEnum


class DistrictEntryRole(StrEnum):
    THROUGH_ROAD = "through_road"
    ENTRY_POINT = "entry_point"

    @classmethod
    def from_wire(cls, key: str | DistrictEntryRole | None) -> DistrictEntryRole | None:
        if key is None:
            return None
        if isinstance(key, cls):
            return key
        norm = str(key).strip().lower()
        for member in cls:
            if member.value == norm:
                return member
        return None
