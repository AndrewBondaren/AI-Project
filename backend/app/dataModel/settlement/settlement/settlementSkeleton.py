"""Settlement instance skeleton — fields on `NamedLocation` (settlement type)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire
from app.dataModel.settlement.area.perimeterBarrier import PerimeterBarrier


class SettlementSkeleton(BaseModel):
    """
    CitySkeleton master-data view — tz_city_generation.md §3, tz_assembler_hierarchy.md §7.1.
    `dominant_material` on import ignored by generator (post-assemble authoritative).
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    economic_tier: DefaultOnWire[str | None] = None
    architectural_style: DefaultOnWire[str | None] = None
    dominant_material: DefaultOnWire[str | None] = None
    settlement_density: DefaultOnWire[str | None] = None
    system_city_size: DefaultOnWire[str | None] = None
    system_location_mood: DefaultOnWire[str | None] = None
    frontage_type_order: DefaultOnWire[list[str] | None] = None
    structure_counts: DefaultOnWire[dict[str, int] | None] = None
    structure_priority: DefaultOnWire[dict[str, int] | None] = None
    perimeter_barrier: DefaultOnWire[PerimeterBarrier | None] = None
