"""default_landforms — bands optional in wire JSON."""

from __future__ import annotations

from pydantic import ConfigDict

from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.annotationPolicy import DefaultOnWire
from app.dataModel.masks.maskCategoryPolicy import MaskCategoryPolicy


class HydrologyLandformsPolicy(MaskCategoryPolicy):
    """default_landforms — MaskCategoryPolicy + optional bands."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    bands: DefaultOnWire[HydrologyBands | None] = None
