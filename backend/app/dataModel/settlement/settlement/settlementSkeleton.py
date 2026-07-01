"""Settlement instance skeleton — fields on `NamedLocation` (settlement type)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.policy import OptionalOnWire


class SettlementSkeleton(BaseModel):
    """
    CitySkeleton master-data view — tz_city_generation.md §3, tz_assembler_hierarchy.md §7.1.
    `dominant_material` on import ignored by generator (post-assemble authoritative).
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    economic_tier: OptionalOnWire[str | None] = None
    architectural_style: OptionalOnWire[str | None] = None
    dominant_material: OptionalOnWire[str | None] = None
    settlement_density: OptionalOnWire[str | None] = None
    system_city_size: OptionalOnWire[str | None] = None
    system_location_mood: OptionalOnWire[str | None] = None
