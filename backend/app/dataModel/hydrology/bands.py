"""bands.min / bands.max — procedural feature width (1..99)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.policy import StrictOnWire

BAND_MIN = 1
BAND_MAX = 99


class HydrologyBands(BaseModel):
    """bands.min / bands.max — procedural feature width (1..99)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    min: StrictOnWire[int] = Field(default=1, ge=BAND_MIN, le=BAND_MAX)
    max: StrictOnWire[int] = Field(default=5, ge=BAND_MIN, le=BAND_MAX)
