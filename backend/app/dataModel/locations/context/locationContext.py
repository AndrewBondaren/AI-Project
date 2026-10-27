"""Frozen transient context — tz_cascade_context §3–§5."""

from typing import Annotated, Self

from pydantic import BaseModel

from app.dataModel.cascade.runtimeContext import CascadeRuntimeContext

from app.dataModel.economy.economyTier.worldEconomyTierRegistry import EconomyTierKey
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.locations.context.cascadeParams import (
    CITY_SIZE,
    DOMINANT_MATERIAL,
    ECONOMIC_TIER,
    FLOOR_MATERIAL,
    SETTLEMENT_DENSITY,
    WALL_MATERIAL,
)
from app.dataModel.locations.settlement.enums.districtDensity import DistrictDensity
from app.dataModel.materials.worldMaterialRegistry import MaterialKey
from app.dataModel.locations.settlement.settlement.worldSettlementSizeRegistry import (
    SettlementSizeKey,
)


class LocationContext(CascadeRuntimeContext[ScopeLevel]):
    economic_tier: Annotated[
        EconomyTierKey | None,
        # The param object from cascadeParams — the same instance the
        # source channels reference by identity.
        ECONOMIC_TIER,
    ] = None
    system_city_size: Annotated[
        SettlementSizeKey | None,
        CITY_SIZE,
    ] = None
    settlement_density: Annotated[
        DistrictDensity | None,
        SETTLEMENT_DENSITY,
    ] = None
    wall_material: Annotated[
        MaterialKey | None,
        WALL_MATERIAL,
    ] = None
    floor_material: Annotated[
        MaterialKey | None,
        FLOOR_MATERIAL,
    ] = None
    dominant_material: Annotated[
        MaterialKey | None,
        DOMINANT_MATERIAL,
    ] = None
    @classmethod
    def root(cls, world: object, *,
             default_sources: tuple[BaseModel, ...] = ()) -> Self:
        """Start at world with no resolution, materialization or default/logging."""
        return cls.at_root(ScopeLevel.WORLD, world, default_sources=default_sources)
