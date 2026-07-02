"""Structure area — perimeter barrier spec (building template + area assembly)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import OptionalOnWire


class PerimeterBarrier(BaseModel):
    """tz_locations.md building perimeter_barrier; StructureAreaAssembler input."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    template: OptionalOnWire[str | None] = None
    probability: OptionalOnWire[float] = Field(default=0.0, ge=0.0, le=1.0)

DEFAULT_PARCEL_MARGIN_M = 1


def perimeter_barrier_from_template(template: dict) -> PerimeterBarrier:
    raw = template.get("perimeter_barrier")
    if raw is None:
        return PerimeterBarrier()
    if isinstance(raw, PerimeterBarrier):
        return raw
    return PerimeterBarrier.model_validate(raw)
