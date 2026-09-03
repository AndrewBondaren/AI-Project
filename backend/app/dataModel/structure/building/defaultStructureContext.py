"""Optional `default_structure_context` on a building layout body — tz_building_generator.md §11.6."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire
from app.dataModel.constrainedField import constrained_field

DEFAULT_FOUNDATION_TYPE = "slab"
DEFAULT_ROOF_TYPE = "gable"
DEFAULT_FOUNDATION_DEPTH = 1


class DefaultStructureContext(BaseModel):
    """Hint for StructureAreaAssembler → StructureContext (not facing / ground_z)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    foundation_type: DefaultOnWire[str] = DEFAULT_FOUNDATION_TYPE
    roof_type: DefaultOnWire[str] = DEFAULT_ROOF_TYPE
    foundation_depth: DefaultOnWire[int] = constrained_field(
        default=DEFAULT_FOUNDATION_DEPTH, greater_equals=0,
    )
    foundation_material: DefaultOnWire[str | None] = None
    roof_material: DefaultOnWire[str | None] = None
    porch_material: DefaultOnWire[str | None] = None
    porch_has_roof: DefaultOnWire[bool] = False
