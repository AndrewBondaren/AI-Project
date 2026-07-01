"""Terrain generation scalars on `worlds` row (not registries)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.policy import OptionalOnWire, StrictOnWire

CHUNK_COLUMNS_MIN = 1
SUBSURFACE_DEPTH_MIN = 10


class WorldTerrainScalars(BaseModel):
    """Scalar terrain/map fields on `worlds` — tz_json_validation.md world row."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    terrain_chunk_columns: OptionalOnWire[int] = Field(default=32, ge=CHUNK_COLUMNS_MIN)
    map_subsurface_depth: OptionalOnWire[int] = Field(default=20, ge=SUBSURFACE_DEPTH_MIN)
    z_min: OptionalOnWire[int | None] = None
    z_max: OptionalOnWire[int | None] = None
    elevation_lapse_rate: OptionalOnWire[float | None] = Field(default=None, ge=0.0)
    g: OptionalOnWire[float] = Field(default=1.0, gt=0.0)
    closed_planet_grid: OptionalOnWire[bool] = False
    magma_band_thickness: OptionalOnWire[int | None] = Field(default=None, ge=0)

    @classmethod
    def canonical_defaults(cls) -> WorldTerrainScalars:
        """Explicit scalars after normalize."""
        return cls(z_min=-500, z_max=8000, elevation_lapse_rate=0.65)
