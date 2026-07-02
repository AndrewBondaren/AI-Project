"""Wire `passage_type` / `system_passage_type` — ENUM-E (tz_locations.md, tz_building_generator.md).

Engine-closed subset for structure generator; N+1 `passage_type_registry` may extend
display types — generator compares via this enum (HY-5).
"""

from __future__ import annotations

from enum import StrEnum


class PassageType(StrEnum):
    STAIRCASE = "staircase"
    DOORWAY = "doorway"
    ARCHWAY = "archway"
    MAIN_ENTRANCE = "main_entrance"
    SERVICE_ENTRANCE = "service_entrance"

    @classmethod
    def from_wire(
        cls,
        key: str | PassageType | None,
        *,
        default: PassageType | None = None,
    ) -> PassageType | None:
        if key is None:
            return default
        if isinstance(key, cls):
            return key
        norm = str(key).strip().lower()
        for member in cls:
            if member.value == norm:
                return member
        return default
