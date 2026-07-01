"""
SCH-WORLD-HYDROLOGY — `worlds.hydrology` JSON.

Not `worlds.caves.hydrology` (отдельный POJO позже).
Эталон: fixtures/world_template.json, docs/tz_terrain_hydrology.md.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

_BAND_MIN = 1
_BAND_MAX = 99


class HydrologyBands(BaseModel):
    """bands.min / bands.max — procedural feature width (1..99)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    min: int = Field(default=1, ge=_BAND_MIN, le=_BAND_MAX)
    max: int = Field(default=5, ge=_BAND_MIN, le=_BAND_MAX)


class HydrologyShoreDefaults(BaseModel):
    """default_shore — REF-W terrain/material for shore cells."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_terrain: str = "shore"
    system_material: str = "sand"


class RiverTypeClassify(BaseModel):
    """default_rivers.type_classify — mountain vs foothill river heuristics (U22)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    mountain_min_source_z: int = 40
    path_mountain_fraction: float = Field(default=0.5, ge=0.0, le=1.0)
    rapid_drop_threshold_m: int = Field(default=3, ge=0)
    mountain_bed_steepness_factor: float = Field(default=1.5, gt=0.0)
    foothill_gradient_threshold: float = Field(default=0.12, ge=0.0)


class HydrologyCategoryPolicy(BaseModel):
    """default_rivers / default_lakes — enabled, autoresolve, bands."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    enabled: bool = True
    autoresolve: bool = True
    bands: HydrologyBands = Field(default_factory=lambda: HydrologyBands(min=1, max=5))


class HydrologyRiversPolicy(HydrologyCategoryPolicy):
    """default_rivers + type_classify."""

    type_classify: RiverTypeClassify = Field(default_factory=RiverTypeClassify)


class HydrologyLakesPolicy(HydrologyCategoryPolicy):
    """default_lakes — same shape as category policy."""


class HydrologyLandformsPolicy(BaseModel):
    """default_landforms — bands optional in wire JSON."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    enabled: bool = True
    autoresolve: bool = True
    bands: HydrologyBands | None = None


class HydrologySeasPolicy(BaseModel):
    """default_seas — coastal_sea + open_ocean."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    enabled: bool = True
    autoresolve_coastal_sea: bool = True
    autoresolve_open_ocean: bool = True
    bands: HydrologyBands = Field(default_factory=lambda: HydrologyBands(min=1, max=20))


class WorldHydrology(BaseModel):
    """Root POJO for `worlds.hydrology`."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    enabled: bool = True
    default_shore: HydrologyShoreDefaults = Field(default_factory=HydrologyShoreDefaults)
    default_rivers: HydrologyRiversPolicy = Field(default_factory=HydrologyRiversPolicy)
    default_lakes: HydrologyLakesPolicy = Field(default_factory=HydrologyLakesPolicy)
    default_seas: HydrologySeasPolicy = Field(default_factory=HydrologySeasPolicy)
    default_landforms: HydrologyLandformsPolicy = Field(default_factory=HydrologyLandformsPolicy)
    materialize_named_locations: bool = False

    @classmethod
    def canonical_empty(cls) -> WorldHydrology:
        """Full explicit blob after normalize (equivalent to missing `{}`)."""
        return cls()
