"""Root POJO for `worlds.hydrology`."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.hydrology.lakes import HydrologyLakesPolicy
from app.dataModel.hydrology.landforms import HydrologyLandformsPolicy
from app.dataModel.hydrology.rivers import HydrologyRiversPolicy
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.hydrology.shore import HydrologyShoreDefaults
from app.dataModel.annotationPolicy import OptionalOnWire


class WorldHydrology(BaseModel):
    """Root POJO for `worlds.hydrology`."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    enabled: OptionalOnWire[bool] = True
    default_shore: OptionalOnWire[HydrologyShoreDefaults] = Field(default_factory=HydrologyShoreDefaults)
    default_rivers: OptionalOnWire[HydrologyRiversPolicy] = Field(default_factory=HydrologyRiversPolicy)
    default_lakes: OptionalOnWire[HydrologyLakesPolicy] = Field(default_factory=HydrologyLakesPolicy)
    default_seas: OptionalOnWire[HydrologySeasPolicy] = Field(default_factory=HydrologySeasPolicy)
    default_landforms: OptionalOnWire[HydrologyLandformsPolicy] = Field(
        default_factory=HydrologyLandformsPolicy,
    )
    materialize_named_locations: OptionalOnWire[bool] = False

    @classmethod
    def canonical_empty(cls) -> WorldHydrology:
        """Full explicit blob after normalize (equivalent to missing `{}`)."""
        return cls()
