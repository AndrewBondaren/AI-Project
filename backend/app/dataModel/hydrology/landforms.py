"""default_landforms — bands optional in wire JSON."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.annotationPolicy import DefaultOnWire


class HydrologyLandformsPolicy(BaseModel):
    """default_landforms — bands optional in wire JSON."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    enabled: DefaultOnWire[bool] = True
    autoresolve: DefaultOnWire[bool] = True
    bands: DefaultOnWire[HydrologyBands | None] = None
