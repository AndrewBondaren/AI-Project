"""default_seas — coastal_sea + open_ocean."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.annotationPolicy import OptionalOnWire


class HydrologySeasPolicy(BaseModel):
    """default_seas — coastal_sea + open_ocean."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    enabled: OptionalOnWire[bool] = True
    autoresolve_coastal_sea: OptionalOnWire[bool] = True
    autoresolve_open_ocean: OptionalOnWire[bool] = True
    bands: OptionalOnWire[HydrologyBands] = Field(default_factory=lambda: HydrologyBands(min=1, max=20))
