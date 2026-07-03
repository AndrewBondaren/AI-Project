"""Reusable min/max blobs in master-data JSON."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.constrainedField import constrained_field


class IntMinMax(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    min: StrictOnWire[int]
    max: StrictOnWire[int]


class PctRange(BaseModel):
    """Fraction range 0..1 — district size_pct width/depth."""
    model_config = ConfigDict(extra="ignore", frozen=True)

    min: StrictOnWire[float] = constrained_field(greater_equals=0.0, lesser_equals=1.0)
    max: StrictOnWire[float] = constrained_field(greater_equals=0.0, lesser_equals=1.0)


class EconomicTierRange(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    min: StrictOnWire[str]
    max: StrictOnWire[str]


class SizePct(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    width: DefaultOnWire[PctRange | None] = None
    depth: DefaultOnWire[PctRange | None] = None
