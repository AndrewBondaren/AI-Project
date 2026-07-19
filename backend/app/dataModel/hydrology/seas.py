"""default_seas — coastal_sea + open_ocean."""

from __future__ import annotations

from pydantic import ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultOnWire
from app.dataModel.constrainedField import constrained_field
from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.masks.maskCategoryPolicy import MaskCategoryPolicy


class HydrologySeasPolicy(MaskCategoryPolicy):
    """default_seas — MaskCategoryPolicy.enabled + coastal/ocean autoresolve flags."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    autoresolve_coastal_sea: DefaultOnWire[bool] = True
    autoresolve_open_ocean: DefaultOnWire[bool] = True
    bands: DefaultOnWire[HydrologyBands] = Field(default_factory=lambda: HydrologyBands(min=1, max=20))
    # Interim bathymetry stub (analog mountain rise_fraction): uniform floor drop vs (z_sea - z_min).
    # Full DepressionForm/Kind pipeline later — tz_terrain_hydrology § Ocean bathymetry.
    stub_drop_fraction_of_span: DefaultOnWire[float] = constrained_field(
        default=0.05, greater_equals=0.0, lesser_equals=1.0,
    )
