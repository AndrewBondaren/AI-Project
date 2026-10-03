"""Root POJO for `worlds.economic_tier_registry`."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

from pydantic import RootModel

from app.dataModel.economy.economyTier import economyTierEntry as _tier_entry_mod
from app.dataModel.economy.economyTier.economyTierEntry import (
    EconomyTierEntry,
    road_modifiers_for,
)
from app.dataModel.registryKey import RegistryKey

if TYPE_CHECKING:
    from app.dataModel.locations.context.cascadeSpec import DefaultPolicy

logger = logging.getLogger(__name__)


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

    def resolve_default(self, policy: DefaultPolicy) -> EconomyTierKey:
        """Domain policy for the cascade; no builtin tier fallback (§3, §5)."""
        # locations package re-exports settlement models that reference this
        # registry. Load the metadata at invocation, after model initialization.
        from app.dataModel.locations.context.cascadeSpec import DefaultPolicy

        match policy:
            case DefaultPolicy.REGISTRY_MEDIAN:
                tiers = self.sorted_by_base_value()
                if not tiers:
                    raise ValueError("economic_tier: cannot resolve median of an empty registry")
                tier = tiers[len(tiers) // 2].system_tier
                logger.warning("economic_tier: no value in cascade; using registry median %r", tier)
                return tier
            case DefaultPolicy.NONE_IS_ERROR:
                raise ValueError("economic_tier: no value after the cascade")
            case DefaultPolicy.CANONICAL_DEFAULT:
                raise ValueError(f"economic_tier: unsupported default policy {policy!r}")
            case _:
                raise ValueError(f"economic_tier: unsupported default policy {policy!r}")


type EconomyTierKey = RegistryKey[WorldEconomyTierRegistry]

_tier_entry_mod.WorldEconomyTierRegistry = WorldEconomyTierRegistry
EconomyTierEntry.model_rebuild()


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
