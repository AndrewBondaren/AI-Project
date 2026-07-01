"""default_shore — REF-W terrain/material for shore cells."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import StrictOnWire


class HydrologyShoreDefaults(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    system_terrain: StrictOnWire[str] = "shore"
    system_material: StrictOnWire[str] = "sand"
