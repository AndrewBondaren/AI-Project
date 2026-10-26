"""Frozen transient context — tz_cascade_context §3–§5."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

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


class LocationContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    level: ScopeLevel
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
    provenance: dict[str, tuple[ScopeLevel, str]] = Field(default_factory=dict)

    # Opaque runtime dependencies for the application resolver (S3): the
    # world accessor and the accumulated per-level link objects. Neither
    # is a context parameter nor serialized; dataModel has no app/db deps.
    _world: object | None = PrivateAttr(default=None)
    _links: dict = PrivateAttr(default_factory=dict)
    # Derived from declared links, never from enum order; runtime node
    # results preserve the snapshot and one-time materialization of
    # ancestors. These are opaque transient state, not wire fields.
    _scope_path: tuple = PrivateAttr(default=())
    _node_results: dict = PrivateAttr(default_factory=dict)
    _default_sources: tuple[BaseModel, ...] = PrivateAttr(default=())

    @classmethod
    def root(cls, world: object, *,
             default_sources: tuple[BaseModel, ...] = ()) -> "LocationContext":
        """Start at world with no resolution, materialization or default/logging."""
        context = cls(level=ScopeLevel.WORLD)
        context._world = world
        context._default_sources = default_sources
        return context
