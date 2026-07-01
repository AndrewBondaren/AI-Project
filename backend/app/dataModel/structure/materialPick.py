"""`pick_from` material selector in structure templates."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import OptionalOnWire, StrictOnWire


class MaterialPick(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    pick_from: StrictOnWire[list[str]] = Field(min_length=1)
