"""Reusable min/max blobs in master-data JSON."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.policy import OptionalOnWire, StrictOnWire


class IntMinMax(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    min: StrictOnWire[int]
    max: StrictOnWire[int]


class PctRange(BaseModel):
    """Fraction range 0..1 — district size_pct width/depth."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    min: StrictOnWire[float] = Field(ge=0.0, le=1.0)
    max: StrictOnWire[float] = Field(ge=0.0, le=1.0)


class EconomicTierRange(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    min: StrictOnWire[str]
    max: StrictOnWire[str]


class SizePct(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    width: OptionalOnWire[PctRange | None] = None
    depth: OptionalOnWire[PctRange | None] = None
