"""Wire `connections[].role` on a district drawing — tz_city_generation.md §9.5.1."""

from __future__ import annotations

from enum import StrEnum


class DistrictStreetRole(StrEnum):
    """Street class inside a district. Not ``DistrictEntryRole`` (through / entry)."""

    MAIN_STREET = "main_street"
    SERVICE_ROAD = "service_road"
    BACK_ALLEY = "back_alley"

    @classmethod
    def from_wire(
        cls,
        key: str | DistrictStreetRole | None,
    ) -> DistrictStreetRole | None:
        if key is None:
            return None
        if isinstance(key, cls):
            return key
        norm = str(key).strip().lower()
        if not norm:
            return None
        for member in cls:
            if member.value == norm:
                return member
        return None

    def frontage_rank(self) -> int:
        return _FRONTAGE_RANK[self]


_FRONTAGE_RANK: dict[DistrictStreetRole, int] = {
    DistrictStreetRole.MAIN_STREET: 0,
    DistrictStreetRole.SERVICE_ROAD: 1,
    DistrictStreetRole.BACK_ALLEY: 2,
}


def frontage_role_rank(role: DistrictStreetRole | None) -> int:
    if role is None:
        return len(_FRONTAGE_RANK)
    return role.frontage_rank()
