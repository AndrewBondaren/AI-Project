"""3D territory AABB for location L2 volumes — WP-21 / LOC-T-3."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.worldPack.territoryVolumePolicy import TerritoryVolumePolicy


class TerritoryVolume(BaseModel):
    """Axis-aligned volume in meter grid coordinates (inclusive bounds)."""

    SCHEMA_ID: ClassVar[str] = "SCH-TERRITORY-VOLUME"

    model_config = ConfigDict(extra="ignore", frozen=True)

    x0: int
    y0: int
    z0: int
    x1: int
    y1: int
    z1: int

    @model_validator(mode="before")
    @classmethod
    def _normalize_bounds(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        x0, x1 = int(data["x0"]), int(data["x1"])
        y0, y1 = int(data["y0"]), int(data["y1"])
        z0, z1 = int(data["z0"]), int(data["z1"])
        return {
            **data,
            "x0": min(x0, x1),
            "x1": max(x0, x1),
            "y0": min(y0, y1),
            "y1": max(y0, y1),
            "z0": min(z0, z1),
            "z1": max(z0, z1),
        }

    def contains(self, x: int, y: int, z: int) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1 and self.z0 <= z <= self.z1


def empty_inclusive(a0: int, a1: int, b0: int, b1: int) -> int:
    """Empty cells between inclusive intervals. Overlap or face-touch → 0."""
    lo_a, hi_a = (a0, a1) if a0 <= a1 else (a1, a0)
    lo_b, hi_b = (b0, b1) if b0 <= b1 else (b1, b0)
    if hi_a < lo_b:
        return lo_b - hi_a - 1
    if hi_b < lo_a:
        return lo_a - hi_b - 1
    return 0


def _intervals_overlap(a0: int, a1: int, b0: int, b1: int) -> bool:
    lo_a, hi_a = (a0, a1) if a0 <= a1 else (a1, a0)
    lo_b, hi_b = (b0, b1) if b0 <= b1 else (b1, b0)
    return lo_a <= hi_b and lo_b <= hi_a


def _axis_separated(a0: int, a1: int, b0: int, b1: int, min_sep: int) -> bool:
    if _intervals_overlap(a0, a1, b0, b1):
        return False
    return empty_inclusive(a0, a1, b0, b1) >= min_sep


def volumes_conflict(
    vol_a: TerritoryVolume,
    vol_b: TerritoryVolume,
    policy: TerritoryVolumePolicy,
) -> bool:
    """True when AABB + XY/Z reserve still overlap on X and Y and Z (LOC-T-3)."""
    separated_x = _axis_separated(
        vol_a.x0, vol_a.x1, vol_b.x0, vol_b.x1, policy.min_settlement_separation_xy,
    )
    separated_y = _axis_separated(
        vol_a.y0, vol_a.y1, vol_b.y0, vol_b.y1, policy.min_settlement_separation_xy,
    )
    separated_z = _axis_separated(
        vol_a.z0, vol_a.z1, vol_b.z0, vol_b.z1, policy.min_settlement_separation_z,
    )
    return (not separated_x) and (not separated_y) and (not separated_z)


def inside_location_volume(
    x: int,
    y: int,
    z: int,
    volumes: list[TerritoryVolume],
) -> bool:
    return any(vol.contains(x, y, z) for vol in volumes)
