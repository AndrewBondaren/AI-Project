"""default_landforms — bands optional in wire JSON."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.policy import OptionalOnWire


class HydrologyLandformsPolicy(BaseModel):
    """default_landforms — bands optional in wire JSON."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    enabled: OptionalOnWire[bool] = True
    autoresolve: OptionalOnWire[bool] = True
    bands: OptionalOnWire[HydrologyBands | None] = None
