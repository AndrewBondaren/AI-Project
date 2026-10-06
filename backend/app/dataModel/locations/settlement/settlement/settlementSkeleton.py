"""Settlement instance skeleton — fields on `NamedLocation` (settlement type)."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal

from pydantic import ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.locations.context.cascadeParams import (
    CITY_SIZE,
    DOMINANT_MATERIAL,
    ECONOMIC_TIER,
    SETTLEMENT_DENSITY,
)
from app.dataModel.cascade.cascadeSpec import CascadeChannel
from app.dataModel.economy.economyTier.worldEconomyTierRegistry import EconomyTierKey
from app.dataModel.materials.worldMaterialRegistry import MaterialKey
from app.dataModel.locations.settlement.enums.districtDensity import DistrictDensity
from app.dataModel.locations.settlement.settlement.settlementPayload import SettlementPayloadFields
from app.dataModel.locations.settlement.settlement.worldLocationMoodRegistry import LocationMoodKey
from app.dataModel.locations.settlement.settlement.worldSettlementSizeRegistry import SettlementSizeKey

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
    `dominant_material` is a cascade channel: authored import value is
    a fallback below the post-assemble layout-derived dominant
    (tz_city_generation.md §3.1, cascade-migration M10).
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
    # Bottom of the `dominant_material` chain — the `above` edge from
    # the settlement NL node is materialized by the verifier (M10).
    dominant_material: Annotated[
        DefaultOnWire[MaterialKey | None],
        CascadeChannel(DOMINANT_MATERIAL, ScopeLevel.SETTLEMENT),
    ] = None
    # Bottom of the `settlement_density` chain — the `above` edges
    # from the NL and district-template nodes are materialized by
    # the verifier.
    settlement_density: Annotated[
        DefaultOnWire[DistrictDensity | None],
        CascadeChannel(SETTLEMENT_DENSITY, ScopeLevel.SETTLEMENT),
    ] = None
    # Bottom of the `system_city_size` chain — mirrors the NL column;
    # the `above` edge from the NL node is materialized by the verifier.
    system_city_size: Annotated[
        DefaultOnWire[SettlementSizeKey | None],
        CascadeChannel(CITY_SIZE, ScopeLevel.SETTLEMENT),
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
