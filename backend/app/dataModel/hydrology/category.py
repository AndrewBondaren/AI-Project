"""default_rivers / default_lakes — shared enabled, autoresolve, bands shape."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.annotationPolicy import OptionalOnWire


class HydrologyCategoryPolicy(BaseModel):
    """default_rivers / default_lakes — enabled, autoresolve, bands."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    enabled: OptionalOnWire[bool] = True
    autoresolve: OptionalOnWire[bool] = True
    bands: OptionalOnWire[HydrologyBands] = Field(default_factory=lambda: HydrologyBands(min=1, max=5))
