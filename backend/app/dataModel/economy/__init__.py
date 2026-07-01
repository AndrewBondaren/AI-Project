"""
SCH-WORLD-ECON-TIER — `worlds.economic_tier_registry` (N1-W-09).

Эталон: fixtures/world_template.json, docs/tz_economic_tier.md.
"""

from app.dataModel.economy.economyTier import EconomyTierEntry, WorldEconomyTierRegistry

__all__ = [
    "EconomyTierEntry",
    "WorldEconomyTierRegistry",
]
