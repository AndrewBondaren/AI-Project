"""Declared building bbox on a plot drawing — packing envelope, not generated rooms.

Runtime packing dataclass lives in ``structureGeneratorService.OccupiedFootprint``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.constrainedField import constrained_field


class OccupiedFootprintSpec(BaseModel):
    """Fine-cell bbox of the building on the plot (origin relative to building origin)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    min_x: DefaultOnWire[int] = 0
    min_y: DefaultOnWire[int] = 0
    width: StrictOnWire[int] = constrained_field(greater_equals=1)
    depth: StrictOnWire[int] = constrained_field(greater_equals=1)
