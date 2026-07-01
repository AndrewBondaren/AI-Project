"""default_rivers — type_classify heuristics + category policy."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.hydrology.category import HydrologyCategoryPolicy
from app.dataModel.annotationPolicy import OptionalOnWire


class RiverTypeClassify(BaseModel):
    """default_rivers.type_classify — mountain vs foothill river heuristics (U22)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    mountain_min_source_z: OptionalOnWire[int] = 40
    path_mountain_fraction: OptionalOnWire[float] = Field(default=0.5, ge=0.0, le=1.0)
    rapid_drop_threshold_m: OptionalOnWire[int] = Field(default=3, ge=0)
    mountain_bed_steepness_factor: OptionalOnWire[float] = Field(default=1.5, gt=0.0)
    foothill_gradient_threshold: OptionalOnWire[float] = Field(default=0.12, ge=0.0)


class HydrologyRiversPolicy(HydrologyCategoryPolicy):
    """default_rivers + type_classify."""

    type_classify: OptionalOnWire[RiverTypeClassify] = Field(default_factory=RiverTypeClassify)
