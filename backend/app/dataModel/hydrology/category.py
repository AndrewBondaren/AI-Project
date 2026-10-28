"""default_rivers / default_lakes — shared enabled, autoresolve, bands shape."""

from __future__ import annotations

from pydantic import ConfigDict, Field

from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.annotationPolicy import DefaultWhenMissing
from app.dataModel.masks.maskCategoryPolicy import MaskCategoryPolicy


class HydrologyCategoryPolicy(MaskCategoryPolicy):
    """default_rivers / default_lakes — MaskCategoryPolicy + bands."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    bands: DefaultWhenMissing[HydrologyBands] = Field(default_factory=lambda: HydrologyBands(min=1, max=5))
