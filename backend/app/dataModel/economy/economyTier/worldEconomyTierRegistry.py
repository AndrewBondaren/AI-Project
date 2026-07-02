"""Root POJO for `worlds.economic_tier_registry`."""

from __future__ import annotations

from typing import ClassVar

from pydantic import RootModel

from app.dataModel.economy.economyTier.economyTierEntry import EconomyTierEntry

_CANONICAL_ENTRIES: tuple[EconomyTierEntry, ...] = (
    EconomyTierEntry(system_tier="poor", display_tier="Хлам", base_value=0),
    EconomyTierEntry(system_tier="basic", display_tier="Базовый", base_value=1),
    EconomyTierEntry(system_tier="standard", display_tier="Стандартный", base_value=10),
    EconomyTierEntry(system_tier="quality", display_tier="Качественный", base_value=100),
    EconomyTierEntry(system_tier="premium", display_tier="Премиальный", base_value=500),
    EconomyTierEntry(system_tier="exceptional", display_tier="Исключительный", base_value=2000),
)

# tz_structure_connections.md §3.7 — road modifiers per tier
_ROAD_DEFAULTS: dict[str, tuple[float, float]] = {
    "poor":        (1.20, 0.6),
    "basic":       (1.10, 0.8),
    "standard":    (1.00, 1.0),
    "quality":     (0.95, 1.3),
    "premium":     (0.95, 1.3),
    "exceptional": (0.90, 1.6),
}


class WorldEconomyTierRegistry(RootModel[list[EconomyTierEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-ECON-TIER"
    """Root POJO for `worlds.economic_tier_registry`. Wire shape: JSON array."""

    root: list[EconomyTierEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldEconomyTierRegistry:
        """fixtures/world_template.json — tiers without explicit road_* fields."""
        return cls(list(_CANONICAL_ENTRIES))

    @classmethod
    def canonical_engine(cls) -> WorldEconomyTierRegistry:
        """Fixture tiers + road_tier_bonus / road_tier_durability from TZ §3.7."""
        entries: list[EconomyTierEntry] = []
        for row in _CANONICAL_ENTRIES:
            bonus, durability = _ROAD_DEFAULTS.get(row.system_tier, (1.0, 1.0))
            entries.append(
                EconomyTierEntry(
                    system_tier=row.system_tier,
                    display_tier=row.display_tier,
                    base_value=row.base_value,
                    road_tier_bonus=bonus,
                    road_tier_durability=durability,
                ),
            )
        return cls(entries)

    def entry_for(self, system_tier: str) -> EconomyTierEntry | None:
        for entry in self.root:
            if entry.system_tier == system_tier:
                return entry
        return None

    def sorted_by_base_value(self) -> list[EconomyTierEntry]:
        return sorted(self.root, key=lambda e: e.base_value)
