"""Runtime building layout body — generate / packing. Not the library Outline.

`BuildingTemplateOutline.levels` is IntMinMax (library). Here `levels` is TZ §3 array.

Nested `levels` / `staircases` / `connections` are still `list[dict]` (**POJO-D-16** / JV-4b).
Target: nested frozen models (same pattern as `perimeter_barrier`, `DistrictConnection`).
Do not reuse `BuildingTemplateRoomSlot` as a generate room.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.constrainedField import constrained_field
from app.dataModel.settlement.area.perimeterBarrier import PerimeterBarrier
from app.dataModel.shared.ranges import EconomicTierRange
from app.dataModel.structure.building.defaultStructureContext import DefaultStructureContext

DEFAULT_Z_HEIGHT = 3


class BuildingLayoutTemplate(BaseModel):
    """One generate-able layout (engine builtin or world override). tz_building_generator.md §3.1."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_name: StrictOnWire[str]
    structure_type: StrictOnWire[str]
    display_name: StrictOnWire[str]
    default_z_height: DefaultOnWire[int] = constrained_field(
        default=DEFAULT_Z_HEIGHT, greater_equals=1,
    )
    economic_tier: DefaultOnWire[str | None] = None
    economic_tier_band: DefaultOnWire[str | None] = None
    economic_tier_range: DefaultOnWire[EconomicTierRange | None] = None
    perimeter_barrier: DefaultOnWire[PerimeterBarrier] = Field(
        default_factory=PerimeterBarrier,
    )
    default_structure_context: DefaultOnWire[DefaultStructureContext] = Field(
        default_factory=DefaultStructureContext,
    )
    levels: DefaultOnWire[list[dict[str, Any]]] = Field(default_factory=list)
    staircases: DefaultOnWire[list[dict[str, Any]]] = Field(default_factory=list)
    connections: DefaultOnWire[list[dict[str, Any]]] = Field(default_factory=list)


def coerce_building_layout(raw: BuildingLayoutTemplate | dict[str, Any]) -> BuildingLayoutTemplate:
    if isinstance(raw, BuildingLayoutTemplate):
        return raw
    return BuildingLayoutTemplate.model_validate(raw)


def try_building_layout(raw: dict[str, Any]) -> BuildingLayoutTemplate | None:
    try:
        return BuildingLayoutTemplate.model_validate(raw)
    except ValidationError:
        return None
