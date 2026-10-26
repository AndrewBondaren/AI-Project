"""Wire `required_structures[].position` — tz_city_generation.md §9.4."""

from __future__ import annotations

from enum import StrEnum


class RequiredStructurePosition(StrEnum):
    """Packing hint on a required plot: geometric center vs first-fit."""

    ANY = "any"
    CENTER = "center"

    @classmethod
    def from_wire(
        cls,
        key: str | RequiredStructurePosition | None,
    ) -> RequiredStructurePosition | None:
        if key is None:
            return None
        if isinstance(key, cls):
            return key
        norm = str(key).strip().lower()
        for member in cls:
            if member.value == norm:
                return member
        return None


POSITION_ANY = RequiredStructurePosition.ANY
POSITION_CENTER = RequiredStructurePosition.CENTER
