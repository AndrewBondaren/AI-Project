"""default_seas — coastal_sea + open_ocean."""

from __future__ import annotations

from pydantic import ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultWhenMissing
from app.dataModel.constrainedField import constrained_field
from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.hydrology.placement.placementFields import WaterCategoryPlacementFields
from app.dataModel.hydrology.shore import HydrologyShoreDefaults
from app.dataModel.masks.maskCategoryPolicy import MaskCategoryPolicy
from app.dataModel.terrain.relief.enums import ReliefConditionTerrain


class HydrologySeasPolicy(MaskCategoryPolicy, WaterCategoryPlacementFields):
    """default_seas — MaskCategoryPolicy.enabled + coastal/ocean autoresolve flags."""

    model_config = ConfigDict(extra="ignore", frozen=True, strict=False, revalidate_instances="never")

    autoresolve_coastal_sea: DefaultWhenMissing[bool] = True
    autoresolve_open_ocean: DefaultWhenMissing[bool] = True
    basin_depth: DefaultWhenMissing[int] = constrained_field(default=20, greater=0)
    max_area_fraction: DefaultWhenMissing[float] = constrained_field(default=0.25, greater=0, lesser_equals=1)
    max_extent_x_fraction: DefaultWhenMissing[float] = constrained_field(default=0.5, greater=0, lesser_equals=1)
    max_extent_y_fraction: DefaultWhenMissing[float] = constrained_field(default=0.5, greater=0, lesser_equals=1)
    min_water_cells: DefaultWhenMissing[int] = constrained_field(default=2, greater_equals=1)
    inland_sea_min_area_fraction: DefaultWhenMissing[float] = constrained_field(default=0.01, greater=0, lesser_equals=1)
    bands: DefaultWhenMissing[HydrologyBands] = Field(default_factory=lambda: HydrologyBands(min=1, max=20))
    shore: DefaultWhenMissing[HydrologyShoreDefaults] = Field(
        default_factory=lambda: HydrologyShoreDefaults.for_condition(
            ReliefConditionTerrain.SHORE_SEA,
        ),
    )
