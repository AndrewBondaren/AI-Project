"""default_seas — coastal_sea + open_ocean."""

from __future__ import annotations

from pydantic import ConfigDict, Field

from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.annotationPolicy import DefaultOnWire
from app.dataModel.masks.maskCategoryPolicy import MaskCategoryPolicy


class HydrologySeasPolicy(MaskCategoryPolicy):
    """default_seas — MaskCategoryPolicy.enabled + coastal/ocean autoresolve flags."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    autoresolve_coastal_sea: DefaultOnWire[bool] = True
    autoresolve_open_ocean: DefaultOnWire[bool] = True
    bands: DefaultOnWire[HydrologyBands] = Field(default_factory=lambda: HydrologyBands(min=1, max=20))
