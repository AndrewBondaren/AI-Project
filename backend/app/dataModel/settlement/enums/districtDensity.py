"""Wire `density` / `settlement_density` keys and street-grid block sizes — tz_structure_connections.md §9."""

from __future__ import annotations

from enum import StrEnum


class DistrictDensity(StrEnum):
    """District / settlement density; owns builtin street-grid block_size (meters)."""

    SPARSE = "sparse"
    MEDIUM = "medium"
    DENSE = "dense"

    @property
    def wire_value(self) -> str:
        return str(self)

    @classmethod
    def from_wire(cls, key: str | DistrictDensity | None) -> DistrictDensity | None:
        if key is None:
            return None
        if isinstance(key, cls):
            return key
        norm = str(key).strip().lower()
        try:
            return cls(norm)
        except ValueError:
            return None

    @classmethod
    def default(cls) -> DistrictDensity:
        return cls.MEDIUM

    @property
    def block_size_m(self) -> int:
        return _BLOCK_SIZE_M[self]

    @classmethod
    def block_size_map(cls) -> dict[str, int]:
        return {member.value: member.block_size_m for member in cls}


_BLOCK_SIZE_M: dict[DistrictDensity, int] = {
    DistrictDensity.SPARSE: 120,
    DistrictDensity.MEDIUM: 80,
    DistrictDensity.DENSE: 50,
}

DEFAULT_BLOCK_SIZE_M = DistrictDensity.MEDIUM.block_size_m


def block_size_for_density(density: DistrictDensity | str | None) -> int:
    member = DistrictDensity.from_wire(density) or DistrictDensity.default()
    return member.block_size_m
