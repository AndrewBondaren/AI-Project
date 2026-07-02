"""default_rivers — type_classify heuristics + category policy."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.hydrology.category import HydrologyCategoryPolicy
from app.dataModel.annotationPolicy import OptionalOnWire
from app.dataModel.constrainedField import constrained_field


class RiverTypeClassify(BaseModel):
    """default_rivers.type_classify — mountain vs foothill river heuristics (U22)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    mountain_min_source_z: OptionalOnWire[int] = 40
    path_mountain_fraction: OptionalOnWire[float] = constrained_field(
        default=0.5, greater_equals=0.0, lesser_equals=1.0,
    )
    rapid_drop_threshold_m: OptionalOnWire[int] = constrained_field(default=3, greater_equals=0)
    mountain_bed_steepness_factor: OptionalOnWire[float] = constrained_field(default=1.5, greater=0.0)
    foothill_gradient_threshold: OptionalOnWire[float] = constrained_field(default=0.12, greater_equals=0.0)


class HydrologyRiversPolicy(HydrologyCategoryPolicy):
    """default_rivers + type_classify."""

    type_classify: OptionalOnWire[RiverTypeClassify] = Field(default_factory=RiverTypeClassify)
