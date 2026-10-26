"""One `worlds.barrier_template_registry[]` row."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire
from app.dataModel.constrainedField import constrained_field
from app.dataModel.registryKey import RegistryKey
from app.dataModel.shared.ranges import IntMinMax
from app.dataModel.locations.structure.materialPick import MaterialPick

if TYPE_CHECKING:
    from app.dataModel.locations.structure.barrier.worldBarrierTemplateRegistry import (
        WorldBarrierTemplateRegistry,
    )


class BarrierTemplateEntry(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    system_type: StrictOnWire[RegistryKey[WorldBarrierTemplateRegistry]]
    glossary_ref: DefaultWhenMissing[str | None] = None
    wall_material: DefaultWhenMissing[MaterialPick | None] = None
    height_levels: DefaultWhenMissing[IntMinMax | None] = None
    gates: DefaultWhenMissing[IntMinMax | None] = None
    towers: DefaultWhenMissing[IntMinMax | None] = None
    width_cells: DefaultWhenMissing[int] = constrained_field(default=1, greater_equals=1)
