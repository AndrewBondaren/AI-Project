"""Assembler skeleton view; settlement channels belong to SettlementPayload."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal

from pydantic import ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.locations.context.cascadeParams import (
    ECONOMIC_TIER,
)
from app.dataModel.cascade.cascadeSpec import CascadeChannel
from app.dataModel.economy.economyTier.worldEconomyTierRegistry import EconomyTierKey
from app.dataModel.locations.settlement.settlement.settlementPayload import SettlementPayloadFields
from app.dataModel.locations.settlement.settlement.worldLocationMoodRegistry import LocationMoodKey

type SettlementSkeletonNlOverlayField = Literal[
    "architectural_style",
    "dominant_material",
    "settlement_density",
    "frontage_type_order",
    "plot_counts",
    "plot_priority",
    "perimeter_barrier",
]
type SettlementSkeletonNlAliasedField = Literal["economic_tier"]
type NamedLocationSkeletonColumn = Literal["system_economic_tier"]


class SettlementSkeleton(SettlementPayloadFields):
    """
    CitySkeleton master-data view — tz_city_generation.md §3, tz_assembler_hierarchy.md §7.1.
    Type-specific fields are plain assembler inputs. SettlementPayload
    declares their cascade channels; this legacy view retains only the
    economic-tier source below the generic NL stamp.
    """

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    # Same names on SQL NamedLocation (CITY-T-1a). Not on NL: economic_tier → system_economic_tier.
    NAMED_LOCATION_OVERLAY_FIELDS: ClassVar[tuple[SettlementSkeletonNlOverlayField, ...]] = (
        "architectural_style",
        "dominant_material",
        "settlement_density",
        "frontage_type_order",
        "plot_counts",
        "plot_priority",
        "perimeter_barrier",
    )
    NAMED_LOCATION_FIELD_ALIASES: ClassVar[
        dict[SettlementSkeletonNlAliasedField, NamedLocationSkeletonColumn]
    ] = {
        "economic_tier": "system_economic_tier",
    }

    # Bottom of the `economic_tier` chain — the `above` edge from
    # NamedLocation.system_economic_tier is materialized by the verifier.
    economic_tier: Annotated[
        DefaultOnWire[EconomyTierKey | None],
        CascadeChannel(ECONOMIC_TIER, ScopeLevel.SETTLEMENT),
    ] = None
    system_location_mood: DefaultOnWire[LocationMoodKey | None] = None


_overlay_unknown = set(SettlementSkeleton.NAMED_LOCATION_OVERLAY_FIELDS) - set(
    SettlementSkeleton.model_fields,
)
_alias_unknown = set(SettlementSkeleton.NAMED_LOCATION_FIELD_ALIASES) - set(
    SettlementSkeleton.model_fields,
)
if _overlay_unknown or _alias_unknown:
    raise RuntimeError(
        "SettlementSkeleton NL map names missing from model_fields: "
        f"overlay={sorted(_overlay_unknown)} aliases={sorted(_alias_unknown)}"
    )
