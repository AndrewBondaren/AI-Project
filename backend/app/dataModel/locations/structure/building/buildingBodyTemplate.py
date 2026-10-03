"""Building body on a plot — envelope context + ``structure`` ref (5o split).

Replaces ``default_structure_context`` on the old mixed layout: the body carries
the structure-envelope hints for ``StructureAreaAssembler → StructureContext``
plus a mandatory uid reference into the global structure library
(``StructureTemplate.system_name``). Plot drawing = ``PlotLayoutTemplate``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.constrainedField import constrained_field
from app.dataModel.locations.structure.building.structureTemplate import StructureKey

DEFAULT_FOUNDATION_TYPE = "slab"
DEFAULT_ROOF_TYPE = "gable"
DEFAULT_FOUNDATION_DEPTH = 1


class BuildingBodyTemplate(BaseModel):
    """Hint for StructureAreaAssembler → StructureContext (not facing / ground_z)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    structure: StrictOnWire[StructureKey]
    foundation_type: DefaultOnWire[str] = DEFAULT_FOUNDATION_TYPE
    roof_type: DefaultOnWire[str] = DEFAULT_ROOF_TYPE
    foundation_depth: DefaultOnWire[int] = constrained_field(
        default=DEFAULT_FOUNDATION_DEPTH, greater_equals=0,
    )
    foundation_material: DefaultOnWire[str | None] = None
    roof_material: DefaultOnWire[str | None] = None
    porch_material: DefaultOnWire[str | None] = None
    porch_has_roof: DefaultOnWire[bool] = False
