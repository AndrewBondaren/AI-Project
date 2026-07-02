"""One `worlds.economic_tier_registry[]` row — N1-W-09."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import OptionalOnWire, StrictOnWire
from app.dataModel.constrainedField import constrained_field


class EconomyTierEntry(BaseModel):
    """tz_economic_tier.md, tz_locations.md § economic_tier_registry."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_tier: StrictOnWire[str]
    display_tier: StrictOnWire[str]
    base_value: StrictOnWire[int] = constrained_field(greater_equals=0)
    road_tier_bonus: OptionalOnWire[float] = constrained_field(default=1.0, greater=0.0)
    road_tier_durability: OptionalOnWire[float] = constrained_field(default=1.0, greater=0.0)

    @classmethod
    def fallback(cls) -> EconomyTierEntry:
        """Field-level builtins for unknown/missing ``system_tier``."""
        return cls(system_tier="__unknown__", display_tier="", base_value=0)
