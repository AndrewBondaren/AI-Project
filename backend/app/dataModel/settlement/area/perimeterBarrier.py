"""Structure area — perimeter barrier spec (building template + area assembly)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire
from app.dataModel.constrainedField import constrained_field
from app.dataModel.spatial.facing import CARDINAL_FACINGS, Facing, parse_facing

if TYPE_CHECKING:
    from app.dataModel.settlement.district.districtTemplateEntry import DistrictTemplateEntry
    from app.dataModel.structure.building.buildingLayoutTemplate import BuildingLayoutTemplate


class PerimeterBarrier(BaseModel):
    """One class, three host instances (settlement / district / parcel) — tz_locations.md."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    template: DefaultOnWire[str | None] = None
    probability: DefaultOnWire[float] = constrained_field(
        default=0.0, greater_equals=0.0, lesser_equals=1.0,
    )
    # None / [] = all four cardinals of this host bbox; resolve skips unknown / intercardinal.
    sides: DefaultOnWire[list[str] | None] = None


def resolved_host_sides(barrier: PerimeterBarrier) -> tuple[frozenset[Facing], list[str]]:
    """
    None / [] = four cardinals of this host bbox.
    Unknown and intercardinal keys are skipped (not an error).
    Empty after skip → four cardinals (same as []).
    """
    raw = barrier.sides
    if not raw:
        return CARDINAL_FACINGS, []
    kept: set[Facing] = set()
    skipped: list[str] = []
    for item in raw:
        try:
            facing = parse_facing(item)
        except ValueError:
            skipped.append(str(item))
            continue
        if facing is None or facing not in CARDINAL_FACINGS:
            skipped.append(str(item))
            continue
        kept.add(facing)
    if not kept:
        return CARDINAL_FACINGS, skipped
    return frozenset(kept), skipped


def perimeter_barrier_from_template(
    template: BuildingLayoutTemplate | DistrictTemplateEntry,
) -> PerimeterBarrier:
    spec = template.perimeter_barrier
    if spec is None:
        return PerimeterBarrier()
    return spec
