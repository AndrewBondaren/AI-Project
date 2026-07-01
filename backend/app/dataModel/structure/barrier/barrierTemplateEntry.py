"""One `worlds.barrier_template_registry[]` row."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import OptionalOnWire, StrictOnWire
from app.dataModel.shared.ranges import IntMinMax
from app.dataModel.structure.materialPick import MaterialPick


class BarrierTemplateEntry(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    system_type: StrictOnWire[str]
    glossary_ref: OptionalOnWire[str | None] = None
    wall_material: OptionalOnWire[MaterialPick | None] = None
    height_levels: OptionalOnWire[IntMinMax | None] = None
    gates: OptionalOnWire[IntMinMax | None] = None
    towers: OptionalOnWire[IntMinMax | None] = None
