"""Assembler skeleton view; settlement channels belong to SettlementPayload."""

from __future__ import annotations

from typing import Annotated

from pydantic import ConfigDict

from app.dataModel.annotationPolicy import DefaultWhenMissing
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.locations.context.cascadeParams import (
    ECONOMIC_TIER,
)
from app.dataModel.cascade.cascadeSpec import CascadeChannel
from app.dataModel.economy.economyTier.worldEconomyTierRegistry import EconomyTierKey
from app.dataModel.locations.settlement.settlement.settlementPayload import SettlementPayloadFields
from app.dataModel.locations.settlement.settlement.worldLocationMoodRegistry import LocationMoodKey

class SettlementSkeleton(SettlementPayloadFields):
    """
    Assembler source/resolved POJO — tz_city_generation.md §3, tz_assembler_hierarchy.md §7.1.
    Type-specific fields are plain assembler inputs. SettlementPayload
    declares their cascade channels; this view retains only the
    economic-tier source below the generic NL stamp.
    """

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    # Bottom of the `economic_tier` chain — the `above` edge from
    # NamedLocation.system_economic_tier is materialized by the verifier.
    economic_tier: Annotated[
        DefaultWhenMissing[EconomyTierKey | None],
        CascadeChannel(ECONOMIC_TIER, ScopeLevel.SETTLEMENT),
    ] = None
    system_location_mood: DefaultWhenMissing[LocationMoodKey | None] = None
