"""Landcover generation knobs in fine cells; no application-side defaults."""

from pydantic import Field

from app.dataModel.annotationPolicy import StrictOnWire
from app.dataModel.masks.maskCategoryPolicy import MaskCategoryPolicy
from app.dataModel.spatial.regionShape import EdgeNoise


class LandcoverRegionsCategoryPolicy(MaskCategoryPolicy):
    seed_spacing: StrictOnWire[int] = Field(gt=0)
    max_radius: StrictOnWire[int] = Field(gt=0)
    claim_noise: StrictOnWire[EdgeNoise]
