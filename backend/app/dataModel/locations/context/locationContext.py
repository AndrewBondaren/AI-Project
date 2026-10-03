"""Frozen transient context — tz_cascade_context §3–§5 (v1: tier only)."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from app.dataModel.economy.economyTier.worldEconomyTierRegistry import EconomyTierKey
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.locations.context.cascadeParams import ECONOMIC_TIER


class LocationContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    level: ScopeLevel
    economic_tier: Annotated[
        EconomyTierKey | None,
        # The param object from cascadeParams — the same instance the
        # source channels reference by identity.
        ECONOMIC_TIER,
    ] = None
    provenance: dict[str, tuple[ScopeLevel, str]] = Field(default_factory=dict)

    # Opaque runtime dependencies for the application resolver (S3): the
    # world accessor and the accumulated per-level link objects. Neither
    # is a context parameter nor serialized; dataModel has no app/db deps.
    _world: object | None = PrivateAttr(default=None)
    _links: dict = PrivateAttr(default_factory=dict)

    @classmethod
    def root(cls, world: object) -> "LocationContext":
        """Start at world with no resolution, materialization or default/logging."""
        context = cls(level=ScopeLevel.WORLD)
        context._world = world
        return context
