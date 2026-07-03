"""Structure area — perimeter barrier spec (building template + area assembly)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire
from app.dataModel.constrainedField import constrained_field


class PerimeterBarrier(BaseModel):
    """tz_locations.md building perimeter_barrier; StructureAreaAssembler input."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    template: DefaultOnWire[str | None] = None
    probability: DefaultOnWire[float] = constrained_field(
        default=0.0, greater_equals=0.0, lesser_equals=1.0,
    )

DEFAULT_PARCEL_MARGIN_M = 1


def perimeter_barrier_from_template(template: dict) -> PerimeterBarrier:
    raw = template.get("perimeter_barrier")
    if raw is None:
        return PerimeterBarrier()
    if isinstance(raw, PerimeterBarrier):
        return raw
    return PerimeterBarrier.model_validate(raw)
