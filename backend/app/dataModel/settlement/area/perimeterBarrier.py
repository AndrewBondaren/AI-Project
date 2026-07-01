"""Structure area — perimeter barrier spec (building template + area assembly)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.policy import OptionalOnWire


class PerimeterBarrier(BaseModel):
    """tz_locations.md building perimeter_barrier; StructureAreaAssembler input."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    template: OptionalOnWire[str | None] = None
    probability: OptionalOnWire[float] = Field(default=0.0, ge=0.0, le=1.0)
