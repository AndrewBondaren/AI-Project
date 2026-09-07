"""District ``placement_conditions[]`` item — tz_city_generation.md §9.3."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictEnumOnWire
from app.dataModel.settlement.settlement.worldSettlementSizeRegistry import SettlementSizeKey


class PlacementConditionType(StrEnum):
    """Wire ``type`` values from city TZ §9.3 plus ``cell_zone``."""

    ADJACENT_TERRAIN = "adjacent_terrain"
    MIN_CITY_SIZE = "min_city_size"
    ECONOMIC_TIER_MIN = "economic_tier_min"
    ECONOMIC_TIER_MAX = "economic_tier_max"
    REQUIRES_DISTRICT_TYPE = "requires_district_type"
    EXCLUDES_DISTRICT_TYPE = "excludes_district_type"
    CELL_ZONE = "cell_zone"


class PlacementCondition(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    type: StrictEnumOnWire[PlacementConditionType]
    terrain_types: DefaultOnWire[list[str] | None] = None
    min_adjacent_cells: DefaultOnWire[int | None] = None
    size: DefaultOnWire[SettlementSizeKey | None] = None
    tier: DefaultOnWire[str | None] = None
    district_type: DefaultOnWire[str | None] = None
    zone: DefaultOnWire[str | None] = None
