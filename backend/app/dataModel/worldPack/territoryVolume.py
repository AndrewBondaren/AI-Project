"""3D territory AABB for location L2 volumes — WP-21."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, model_validator


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


def inside_location_volume(
    x: int,
    y: int,
    z: int,
    volumes: list[TerritoryVolume],
) -> bool:
    return any(vol.contains(x, y, z) for vol in volumes)
