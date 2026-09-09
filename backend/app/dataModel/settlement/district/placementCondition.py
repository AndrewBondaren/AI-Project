"""District ``placement_conditions[]`` item — tz_city_generation.md §9.3."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictEnumOnWire
from app.dataModel.economy.economyTier.worldEconomyTierRegistry import EconomyTierKey
from app.dataModel.settlement.district.cellZone import CellZone
from app.dataModel.settlement.settlement.worldSettlementSizeRegistry import SettlementSizeKey
from app.dataModel.terrain.worldTerrainRegistry import TerrainKey


class PlacementConditionType(StrEnum):
    """Wire ``type`` values from city TZ §9.3 plus ``cell_zone``."""

    ADJACENT_TERRAIN = "adjacent_terrain"
    MIN_SETTLEMENT_SIZE = "min_settlement_size"
    ECONOMIC_TIER_MIN = "economic_tier_min"
    ECONOMIC_TIER_MAX = "economic_tier_max"
    REQUIRES_DISTRICT_TYPE = "requires_district_type"
    EXCLUDES_DISTRICT_TYPE = "excludes_district_type"
    CELL_ZONE = "cell_zone"

    @classmethod
    def _missing_(cls, value: object) -> PlacementConditionType | None:
        if isinstance(value, str) and value.strip().lower() == "min_city_size":
            return cls.MIN_SETTLEMENT_SIZE
        return None


class PlacementCondition(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    type: StrictEnumOnWire[PlacementConditionType]
    terrain_types: DefaultOnWire[list[TerrainKey] | None] = None
    min_adjacent_cells: DefaultOnWire[int | None] = None
    size: DefaultOnWire[SettlementSizeKey | None] = None
    tier: DefaultOnWire[EconomyTierKey | None] = None
    district_type: DefaultOnWire[str | None] = None
    zone: DefaultOnWire[CellZone | None] = None
