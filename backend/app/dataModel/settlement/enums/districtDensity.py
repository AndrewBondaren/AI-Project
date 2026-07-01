"""Wire `density` / `settlement_density` keys and street-grid block sizes — tz_structure_connections.md §9."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class _DistrictDensityBuiltin:
    block_size_m: int


class DistrictDensity(Enum):
    """District / settlement density; owns builtin street-grid block_size (meters)."""

    SPARSE = _DistrictDensityBuiltin(120)
    MEDIUM = _DistrictDensityBuiltin(80)
    DENSE = _DistrictDensityBuiltin(50)

    @property
    def wire_value(self) -> str:
        return self.name.lower()

    def __str__(self) -> str:
        return self.wire_value

    @classmethod
    def from_wire(cls, key: str | None) -> DistrictDensity | None:
        norm = (key or "").strip().lower()
        for member in cls:
            if member.wire_value == norm:
                return member
        return None

    @classmethod
    def default(cls) -> DistrictDensity:
        return cls.MEDIUM

    @property
    def block_size_m(self) -> int:
        return self.value.block_size_m

    @classmethod
    def block_size_map(cls) -> dict[str, int]:
        return {member.wire_value: member.block_size_m for member in cls}


DEFAULT_BLOCK_SIZE_M = DistrictDensity.MEDIUM.block_size_m


def block_size_for_density(density: str | None) -> int:
    member = DistrictDensity.from_wire(density) or DistrictDensity.default()
    return member.block_size_m
