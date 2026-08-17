"""default_lakes — same shape as category policy."""

from __future__ import annotations

from pydantic import Field

from app.dataModel.annotationPolicy import DefaultOnWire
from app.dataModel.hydrology.category import HydrologyCategoryPolicy
from app.dataModel.hydrology.shore import HydrologyShoreDefaults
from app.dataModel.terrain.relief.enums import ReliefConditionTerrain


class HydrologyLakesPolicy(HydrologyCategoryPolicy):
    """default_lakes — same shape as category policy."""

    shore: DefaultOnWire[HydrologyShoreDefaults] = Field(
        default_factory=lambda: HydrologyShoreDefaults.for_condition(
            ReliefConditionTerrain.SHORE_LAKE,
        ),
    )
