"""Frozen transient context — tz_cascade_context §3–§5 (v1: tier only)."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from app.dataModel.economy.economyTier.worldEconomyTierRegistry import EconomyTierKey
from app.dataModel.locations.context.cascadeLevel import CascadeLevel
from app.dataModel.locations.context.cascadeParams import ECONOMIC_TIER


class LocationContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    level: CascadeLevel
    economic_tier: Annotated[
        EconomyTierKey | None,
        # The param object from cascadeParams — the same instance the
        # source channels reference by identity.
        ECONOMIC_TIER,
    ] = None
    provenance: dict[str, tuple[CascadeLevel, str]] = Field(default_factory=dict)

    # Opaque runtime dependency for S3. It is neither a context parameter nor
    # a serialized field; dataModel does not depend on db or application.
    _world: object | None = PrivateAttr(default=None)

    @classmethod
    def root(cls, world: object) -> "LocationContext":
        """Start at world with no resolution, materialization or default/logging."""
        context = cls(level=CascadeLevel.WORLD)
        context._world = world
        return context
