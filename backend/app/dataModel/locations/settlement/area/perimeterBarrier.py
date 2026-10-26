"""Structure area — perimeter barrier spec (building template + area assembly)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, field_validator

from app.dataModel.annotationPolicy import DefaultWhenMissing
from app.dataModel.constrainedField import constrained_field
from app.dataModel.registryKey import RegistryKey
from app.dataModel.spatial.facing import CARDINAL_FACINGS, Facing, parse_facing

if TYPE_CHECKING:
    from app.dataModel.locations.settlement.district.districtTemplateEntry import DistrictTemplateEntry
    from app.dataModel.locations.structure.barrier.worldBarrierTemplateRegistry import (
        WorldBarrierTemplateRegistry,
    )
    from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate

logger = logging.getLogger(__name__)


def coerce_cardinal_barrier_sides(value: Any) -> list[Facing] | None:
    """Validate host cardinals; preserve aliases and deduplicate valid values."""
    if value is None:
        return None
    if not isinstance(value, (list, tuple)):
        raise ValueError("sides expected list of cardinal facings")
    kept: list[Facing] = []
    seen: set[Facing] = set()
    for item in value:
        facing: Facing | None
        try:
            facing = parse_facing(item) if not isinstance(item, Facing) else item
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid host cardinal: {item!r}") from exc
        if facing is None or facing not in CARDINAL_FACINGS:
            raise ValueError(f"invalid host cardinal: {item!r}")
        if facing in seen:
            continue
        seen.add(facing)
        kept.append(facing)
    return kept


type CardinalBarrierSides = Annotated[
    list[Facing] | None,
    BeforeValidator(coerce_cardinal_barrier_sides),
]


class PerimeterBarrier(BaseModel):
    """One class, three host instances (settlement / district / parcel) — tz_locations.md."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    template: DefaultWhenMissing[RegistryKey[WorldBarrierTemplateRegistry] | None] = None
    probability: DefaultWhenMissing[float] = constrained_field(
        default=0.0, greater_equals=0.0, lesser_equals=1.0,
    )
    # None / [] = all four cardinals of this host bbox.
    sides: DefaultWhenMissing[CardinalBarrierSides] = None

    @field_validator("template", mode="before")
    @classmethod
    def _blank_template_is_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value


def resolved_host_sides(barrier: PerimeterBarrier) -> tuple[frozenset[Facing], list[str]]:
    """None / [] = all host cardinals; invalid values never become all sides."""
    sides = coerce_cardinal_barrier_sides(barrier.sides)
    return (frozenset(sides) if sides else CARDINAL_FACINGS), []


def perimeter_barrier_from_template(
    template: PlotLayoutTemplate | DistrictTemplateEntry,
) -> PerimeterBarrier:
    spec = template.perimeter_barrier
    if spec is None:
        return PerimeterBarrier()
    return spec
