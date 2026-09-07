"""
SCH-WORLD-ECON-TIER — `worlds.economic_tier_registry` (N1-W-09).

Эталон: fixtures/world_template.json, docs/tz_economic_tier.md.
"""

from app.dataModel.economy.economyTier import (
    EconomyTierEntry,
    EconomyTierKey,
    WorldEconomyTierRegistry,
)
from app.dataModel.economy.enums import (
    BAND_COMMON,
    BAND_MIDDLE,
    BAND_POOR,
    BAND_RICH,
    BAND_WEALTHY,
    DEFAULT_SIDEWALK_WIDTH_CELLS,
    EconomicTierBand,
    SidewalkWidthDefault,
    sidewalk_width_for_band,
)

__all__ = [
    "BAND_COMMON",
    "BAND_MIDDLE",
    "BAND_POOR",
    "BAND_RICH",
    "BAND_WEALTHY",
    "DEFAULT_SIDEWALK_WIDTH_CELLS",
    "EconomyTierEntry",
    "EconomyTierKey",
    "EconomicTierBand",
    "SidewalkWidthDefault",
    "WorldEconomyTierRegistry",
    "sidewalk_width_for_band",
]
