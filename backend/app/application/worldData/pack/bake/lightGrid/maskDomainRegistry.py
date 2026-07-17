"""Contributor registry — builds DEFAULT_CONTRIBUTORS from dataModel SoT.

tz_map_light_bake § Hybrid C. Order SoT: ``COMPOSE_CONTRIBUTOR_ORDER``.
"""

from __future__ import annotations

from collections.abc import Callable

from app.application.worldData.pack.bake.lightGrid.contributor import LightGridContributor
from app.application.worldData.pack.bake.lightGrid.contributors.climate import ClimateContributor
from app.application.worldData.pack.bake.lightGrid.contributors.hydro import HydroContributor
from app.application.worldData.pack.bake.lightGrid.contributors.landcover import LandcoverContributor
from app.application.worldData.pack.bake.lightGrid.contributors.mountain import MountainContributor
from app.application.worldData.pack.bake.lightGrid.contributors.ravine import RavineContributor
from app.application.worldData.pack.bake.lightGrid.contributors.relief import ReliefContributor
from app.application.worldData.pack.bake.lightGrid.contributors.road import RoadContributor
from app.application.worldData.pack.bake.lightGrid.contributors.settlement import (
    SettlementContributor,
)
from app.dataModel.masks.enums.maskDomainId import (
    COMPOSE_CONTRIBUTOR_ORDER,
    MASK_DOMAIN_CONTRIBUTOR,
    MaskDomainId,
    LightContributorId,
)

_CONTRIBUTOR_FACTORY: dict[LightContributorId, Callable[[], LightGridContributor]] = {
    LightContributorId.RELIEF: ReliefContributor,
    LightContributorId.CLIMATE: ClimateContributor,
    LightContributorId.LANDCOVER: LandcoverContributor,
    LightContributorId.MOUNTAIN: MountainContributor,
    LightContributorId.RAVINE: RavineContributor,
    LightContributorId.HYDRO: HydroContributor,
    LightContributorId.SETTLEMENT: SettlementContributor,
    LightContributorId.ROAD: RoadContributor,
}


def build_default_contributors() -> tuple[LightGridContributor, ...]:
    """Instantiate pipeline from ``COMPOSE_CONTRIBUTOR_ORDER`` (single SoT)."""
    missing = [c for c in COMPOSE_CONTRIBUTOR_ORDER if c not in _CONTRIBUTOR_FACTORY]
    if missing:
        raise RuntimeError(f"no factory for compose contributors: {missing!r}")
    contributors = tuple(_CONTRIBUTOR_FACTORY[c]() for c in COMPOSE_CONTRIBUTOR_ORDER)
    for expected, contrib in zip(COMPOSE_CONTRIBUTOR_ORDER, contributors, strict=True):
        if contrib.name != expected.value:
            raise RuntimeError(
                f"contributor name mismatch: factory {expected!r} produced name={contrib.name!r}"
            )
    return contributors


def contributor_for_mask_domain(domain: MaskDomainId) -> LightContributorId:
    return MASK_DOMAIN_CONTRIBUTOR[domain]
