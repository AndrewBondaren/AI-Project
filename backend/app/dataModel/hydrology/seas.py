"""default_seas — coastal_sea + open_ocean."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.annotationPolicy import DefaultOnWire


class HydrologySeasPolicy(BaseModel):
    """default_seas — coastal_sea + open_ocean."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    enabled: DefaultOnWire[bool] = True
    autoresolve_coastal_sea: DefaultOnWire[bool] = True
    autoresolve_open_ocean: DefaultOnWire[bool] = True
    bands: DefaultOnWire[HydrologyBands] = Field(default_factory=lambda: HydrologyBands(min=1, max=20))
