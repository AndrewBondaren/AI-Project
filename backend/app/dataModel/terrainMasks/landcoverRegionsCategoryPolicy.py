"""Landcover generation knobs in fine cells; no application-side defaults."""

from pydantic import Field

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire
from app.dataModel.masks.maskCategoryPolicy import MaskCategoryPolicy
from app.dataModel.spatial.regionShape import EdgeNoise


class LandcoverRegionsCategoryPolicy(MaskCategoryPolicy):
    transition_threshold: DefaultWhenMissing[float] = Field(default=1.0, gt=0, le=1, allow_inf_nan=False)
    seed_spacing: StrictOnWire[int] = Field(gt=0)
    max_radius: StrictOnWire[int] = Field(gt=0)
    claim_noise: StrictOnWire[EdgeNoise]
