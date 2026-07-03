"""One `worlds.barrier_template_registry[]` row."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.shared.ranges import IntMinMax
from app.dataModel.structure.materialPick import MaterialPick


class BarrierTemplateEntry(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    system_type: StrictOnWire[str]
    glossary_ref: DefaultOnWire[str | None] = None
    wall_material: DefaultOnWire[MaterialPick | None] = None
    height_levels: DefaultOnWire[IntMinMax | None] = None
    gates: DefaultOnWire[IntMinMax | None] = None
    towers: DefaultOnWire[IntMinMax | None] = None
