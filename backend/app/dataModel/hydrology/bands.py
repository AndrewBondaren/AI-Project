"""bands.min / bands.max — procedural feature width (1..99)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import StrictOnWire
from app.dataModel.constrainedField import constrained_field

BAND_MIN = 1
BAND_MAX = 99


class HydrologyBands(BaseModel):
    """bands.min / bands.max — procedural feature width (1..99)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    min: StrictOnWire[int] = constrained_field(
        default=1, greater_equals=BAND_MIN, lesser_equals=BAND_MAX,
    )
    max: StrictOnWire[int] = constrained_field(
        default=5, greater_equals=BAND_MIN, lesser_equals=BAND_MAX,
    )
