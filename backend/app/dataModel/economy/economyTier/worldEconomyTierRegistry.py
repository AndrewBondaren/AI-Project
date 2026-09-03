"""Root POJO for `worlds.economic_tier_registry`."""

from __future__ import annotations

from typing import ClassVar

from pydantic import RootModel

from app.dataModel.economy.economyTier.economyTierEntry import (
    EconomyTierEntry,
    road_modifiers_for,
)


def _canonical_entry(
    system_tier: str,
    display_tier: str,
    base_value: int,
) -> EconomyTierEntry:
    bonus, durability = road_modifiers_for(system_tier)
    return EconomyTierEntry(
        system_tier=system_tier,
        display_tier=display_tier,
        base_value=base_value,
        road_tier_bonus=bonus,
        road_tier_durability=durability,
    )


_CANONICAL_ENTRIES: tuple[EconomyTierEntry, ...] = (
    _canonical_entry("poor", "Хлам", 0),
    _canonical_entry("basic", "Базовый", 1),
    _canonical_entry("standard", "Стандартный", 10),
    _canonical_entry("quality", "Качественный", 100),
    _canonical_entry("premium", "Премиальный", 500),
    _canonical_entry("exceptional", "Исключительный", 2000),
)


class WorldEconomyTierRegistry(RootModel[list[EconomyTierEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-ECON-TIER"
    """Root POJO for `worlds.economic_tier_registry`. Wire shape: JSON array."""

    root: list[EconomyTierEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldEconomyTierRegistry:
        """fixtures/world_template.json + TZ §3.7 road modifiers."""
        return cls(list(_CANONICAL_ENTRIES))

    @classmethod
    def canonical_engine(cls) -> WorldEconomyTierRegistry:
        """Same builtins as ``canonical_defaults`` — one SoT for road_tier_*."""
        return cls.canonical_defaults()

    def entry_for(self, system_tier: str) -> EconomyTierEntry | None:
        for entry in self.root:
            if entry.system_tier == system_tier:
                return entry
        return None

    def sorted_by_base_value(self) -> list[EconomyTierEntry]:
        return sorted(self.root, key=lambda e: e.base_value)
