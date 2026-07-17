"""Engine mask-domain ids + light compose contributor ids — tz_map_light_bake § Hybrid C.

Not N+1: new member = engine PR. Climate biomes (tundra, volcanic) are not
MaskDomainId values — see climate_zone_registry.
"""

from __future__ import annotations

from enum import StrEnum


class MaskDomainId(StrEnum):
    """Structural L0 mask writers (compose contributors bound to policy roots)."""

    HYDROLOGY = "hydrology"
    MOUNTAINS = "mountains"
    FORESTS = "forests"
    PLAINS = "plains"
    RAVINES = "ravines"
    ROADS = "roads"
    SETTLEMENT = "settlement"


class LightContributorId(StrEnum):
    """``LightGridContributor.name`` SoT — bake pipeline members."""

    RELIEF = "relief"
    CLIMATE = "climate"
    LANDCOVER = "landcover"
    MOUNTAIN = "mountain"
    RAVINE = "ravine"
    HYDRO = "hydro"
    SETTLEMENT = "settlement"
    ROAD = "road"


# Domains that compete on ``system_terrain`` — high → low (road wins over plains).
TERRAIN_MERGE_RANK_HIGH_TO_LOW: tuple[MaskDomainId, ...] = (
    MaskDomainId.ROADS,
    MaskDomainId.RAVINES,
    MaskDomainId.MOUNTAINS,
    MaskDomainId.FORESTS,
    MaskDomainId.PLAINS,
)

# Mask domain → contributor that materializes it (forests+plains share landcover).
MASK_DOMAIN_CONTRIBUTOR: dict[MaskDomainId, LightContributorId] = {
    MaskDomainId.FORESTS: LightContributorId.LANDCOVER,
    MaskDomainId.PLAINS: LightContributorId.LANDCOVER,
    MaskDomainId.MOUNTAINS: LightContributorId.MOUNTAIN,
    MaskDomainId.RAVINES: LightContributorId.RAVINE,
    MaskDomainId.HYDROLOGY: LightContributorId.HYDRO,
    MaskDomainId.SETTLEMENT: LightContributorId.SETTLEMENT,
    MaskDomainId.ROADS: LightContributorId.ROAD,
}

# Single SoT for compose call order (Base → Context → Landcover → Structural → Hydro → Culture).
COMPOSE_CONTRIBUTOR_ORDER: tuple[LightContributorId, ...] = (
    LightContributorId.RELIEF,
    LightContributorId.CLIMATE,
    LightContributorId.LANDCOVER,
    LightContributorId.MOUNTAIN,
    LightContributorId.RAVINE,
    LightContributorId.HYDRO,
    LightContributorId.SETTLEMENT,
    LightContributorId.ROAD,
)
