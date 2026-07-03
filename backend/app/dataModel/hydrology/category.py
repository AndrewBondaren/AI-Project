"""default_rivers / default_lakes — shared enabled, autoresolve, bands shape."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.annotationPolicy import DefaultOnWire


class HydrologyCategoryPolicy(BaseModel):
    """default_rivers / default_lakes — enabled, autoresolve, bands."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    enabled: DefaultOnWire[bool] = True
    autoresolve: DefaultOnWire[bool] = True
    bands: DefaultOnWire[HydrologyBands] = Field(default_factory=lambda: HydrologyBands(min=1, max=5))
