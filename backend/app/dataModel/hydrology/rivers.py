"""default_rivers — type_classify heuristics + category policy."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.hydrology.category import HydrologyCategoryPolicy
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.hydrology.shore import HydrologyShoreDefaults
from app.dataModel.annotationPolicy import DefaultWhenMissing
from app.dataModel.constrainedField import constrained_field
from app.dataModel.terrain.relief.enums import ReliefConditionTerrain


class RiverTypeClassify(BaseModel):
    """default_rivers.type_classify — mountain vs foothill river heuristics (U22)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    mountain_min_source_z: DefaultWhenMissing[int] = 40
    path_mountain_fraction: DefaultWhenMissing[float] = constrained_field(
        default=0.5, greater_equals=0.0, lesser_equals=1.0,
    )
    rapid_drop_threshold_m: DefaultWhenMissing[int] = constrained_field(default=3, greater_equals=0)
    mountain_bed_steepness_factor: DefaultWhenMissing[float] = constrained_field(default=1.5, greater=0.0)
    foothill_gradient_threshold: DefaultWhenMissing[float] = constrained_field(default=0.12, greater_equals=0.0)


class HydrologyRiversPolicy(HydrologyCategoryPolicy):
    """default_rivers + type_classify."""

    channel_depth_cells: DefaultWhenMissing[int] = constrained_field(default=3, greater=0, strict=True)
    mouth_search_radius_fine: DefaultWhenMissing[int] = constrained_field(default=200, greater_equals=0, strict=True)
    max_path_cells: DefaultWhenMissing[int] = constrained_field(default=128, greater_equals=2, strict=True)
    type_classify: DefaultWhenMissing[RiverTypeClassify] = Field(default_factory=RiverTypeClassify)
    shore: DefaultWhenMissing[HydrologyShoreDefaults] = Field(
        default_factory=lambda: HydrologyShoreDefaults.for_condition(
            ReliefConditionTerrain.SHORE_RIVER,
        ),
    )
    mountain_shore: DefaultWhenMissing[HydrologyShoreDefaults] = Field(
        default_factory=lambda: HydrologyShoreDefaults.for_condition(
            ReliefConditionTerrain.SHORE_MOUNTAIN_RIVER,
        ),
    )

    def channel_depth_for(self, connection_type: HydrologyConnectionType) -> int:
        """Vertical cell depth; mountain multiplier retains the existing rounding."""
        if connection_type is HydrologyConnectionType.MOUNTAIN_RIVER:
            return max(1, round(self.channel_depth_cells * self.type_classify.mountain_bed_steepness_factor))
        if connection_type is HydrologyConnectionType.RIVER:
            return self.channel_depth_cells
        raise ValueError("river channel depth requires a river connection type")
