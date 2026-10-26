"""default_lakes — same shape as category policy."""

from __future__ import annotations

from pydantic import Field

from app.dataModel.annotationPolicy import DefaultWhenMissing
from app.dataModel.constrainedField import constrained_field
from app.dataModel.hydrology.category import HydrologyCategoryPolicy
from app.dataModel.hydrology.shore import HydrologyShoreDefaults
from app.dataModel.terrain.relief.enums import ReliefConditionTerrain


class HydrologyLakesPolicy(HydrologyCategoryPolicy):
    """default_lakes — same shape as category policy."""

    basin_depth: DefaultWhenMissing[int] = constrained_field(default=5, greater=0)
    min_water_cells: DefaultWhenMissing[int] = constrained_field(default=2, greater_equals=1)

    shore: DefaultWhenMissing[HydrologyShoreDefaults] = Field(
        default_factory=lambda: HydrologyShoreDefaults.for_condition(
            ReliefConditionTerrain.SHORE_LAKE,
        ),
    )
