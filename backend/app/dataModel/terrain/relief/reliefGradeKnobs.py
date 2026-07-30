"""Shared grade knobs (weights / shoulder / attachments) — tz_terrain_relief R22/R27/R28."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.constrainedField import constrained_field

WEIGHT_SUM_EPS = 1e-6


def weights_sum_ok(slope_weight: float, sheer_weight: float) -> bool:
    return abs(float(slope_weight) + float(sheer_weight) - 1.0) <= WEIGHT_SUM_EPS


class ReliefGradeKnobs(BaseModel):
    """Weights + optional shoulder/attachments — on Mode A case or Mode B band."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    slope_weight: StrictOnWire[float] = constrained_field(
        greater_equals=0.0, lesser_equals=1.0,
    )
    sheer_weight: StrictOnWire[float] = constrained_field(
        greater_equals=0.0, lesser_equals=1.0,
    )
    shoulder_width_cells: DefaultOnWire[int] = Field(default=1, ge=0)
    earthen_canal: DefaultOnWire[bool] = False
    structure_refs: DefaultOnWire[list[str]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _weights_sum_one(self) -> ReliefGradeKnobs:
        if not weights_sum_ok(self.slope_weight, self.sheer_weight):
            raise ValueError(
                f"slope_weight + sheer_weight must == 1 (±{WEIGHT_SUM_EPS}); "
                f"got {self.slope_weight}+{self.sheer_weight}"
            )
        return self
