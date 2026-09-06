"""Settlement instance skeleton — fields on `NamedLocation` (settlement type)."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire
from app.dataModel.settlement.area.perimeterBarrier import PerimeterBarrier
from app.dataModel.settlement.settlement.settlementSpecializationBind import (
    SettlementSpecializationBind,
)
from app.dataModel.settlement.settlement.typicalDistrictRef import TypicalDistrictRef


class SettlementSkeleton(BaseModel):
    """
    CitySkeleton master-data view — tz_city_generation.md §3, tz_assembler_hierarchy.md §7.1.
    `dominant_material` on import ignored by generator (post-assemble authoritative).
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    # Same names on SQL NamedLocation (CITY-T-1a). Not on NL: economic_tier → system_economic_tier.
    NAMED_LOCATION_OVERLAY_FIELDS: ClassVar[tuple[str, ...]] = (
        "architectural_style",
        "dominant_material",
        "settlement_density",
        "frontage_type_order",
        "structure_counts",
        "structure_priority",
        "perimeter_barrier",
    )
    NAMED_LOCATION_FIELD_ALIASES: ClassVar[dict[str, str]] = {
        "economic_tier": "system_economic_tier",
    }

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
    typical_districts: DefaultOnWire[list[TypicalDistrictRef] | None] = None
    system_settlement_specializations: DefaultOnWire[
        list[SettlementSpecializationBind] | None
    ] = None
