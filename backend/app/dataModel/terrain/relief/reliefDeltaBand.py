"""Mode B delta_z band — tz_terrain_relief R32."""

from __future__ import annotations

from pydantic import ConfigDict, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.constrainedField import constrained_field
from app.dataModel.terrain.relief.reliefGradeKnobs import ReliefGradeKnobs


class ReliefDeltaBand(ReliefGradeKnobs):
    """One inclusive Δz interval with knobs (Mode B)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    delta_z_min: StrictOnWire[int] = constrained_field(greater_equals=1)
    delta_z_max: DefaultOnWire[int | None] = None

    @model_validator(mode="after")
    def _max_ge_min(self) -> ReliefDeltaBand:
        if self.delta_z_max is not None and self.delta_z_max < self.delta_z_min:
            raise ValueError(
                f"delta_z_max ({self.delta_z_max}) < delta_z_min ({self.delta_z_min})"
            )
        return self
