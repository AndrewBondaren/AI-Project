"""default_rivers — type_classify heuristics + category policy."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.hydrology.category import HydrologyCategoryPolicy
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
