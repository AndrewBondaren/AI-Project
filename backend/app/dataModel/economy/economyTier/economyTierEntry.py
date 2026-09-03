"""One `worlds.economic_tier_registry[]` row — N1-W-09."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.annotationPolicy import IgnoreOnWire, StrictOnWire
from app.dataModel.constrainedField import constrained_field

# Neutral modifiers: unknown tier; TZ §3.7 natural terrain (material=null).
NEUTRAL_ROAD_TIER_BONUS = 1.0
NEUTRAL_ROAD_TIER_DURABILITY = 1.0

# tz_structure_connections.md §3.7 — builtin road modifiers per system_tier.
# ``quality`` is in the fixture registry; TZ table omits it (same pair as premium).
ROAD_TIER_DEFAULTS: dict[str, tuple[float, float]] = {
    "poor":        (1.20, 0.6),
    "basic":       (1.10, 0.8),
    "standard":    (1.00, 1.0),
    "quality":     (0.95, 1.3),
    "premium":     (0.95, 1.3),
    "exceptional": (0.90, 1.6),
}


def road_modifiers_for(system_tier: str) -> tuple[float, float]:
    """TZ §3.7 pair for a known ``system_tier``; else neutral 1.0 / 1.0."""
    return ROAD_TIER_DEFAULTS.get(
        system_tier,
        (NEUTRAL_ROAD_TIER_BONUS, NEUTRAL_ROAD_TIER_DURABILITY),
    )


class EconomyTierEntry(BaseModel):
    """tz_economic_tier.md, tz_locations.md § economic_tier_registry."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_tier: StrictOnWire[str]
    display_tier: StrictOnWire[str]
    base_value: StrictOnWire[int] = constrained_field(greater_equals=0)
    # IgnoreOnWire: omitted keys must not be stamped with the neutral 1.0 before
    # validate — ``_fill_omitted_road_modifiers`` applies per-tier TZ defaults.
    road_tier_bonus: IgnoreOnWire[float] = constrained_field(
        default=NEUTRAL_ROAD_TIER_BONUS, greater=0.0,
    )
    road_tier_durability: IgnoreOnWire[float] = constrained_field(
        default=NEUTRAL_ROAD_TIER_DURABILITY, greater=0.0,
    )

    @model_validator(mode="before")
    @classmethod
    def _fill_omitted_road_modifiers(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        tier = data.get("system_tier")
        if not isinstance(tier, str):
            return data
        bonus, durability = road_modifiers_for(tier)
        missing_bonus = "road_tier_bonus" not in data
        missing_durability = "road_tier_durability" not in data
        if not missing_bonus and not missing_durability:
            return data
        out = dict(data)
        if missing_bonus:
            out["road_tier_bonus"] = bonus
        if missing_durability:
            out["road_tier_durability"] = durability
        return out

    @classmethod
    def fallback(cls) -> EconomyTierEntry:
        """Field-level builtins for unknown/missing ``system_tier``."""
        return cls(system_tier="__unknown__", display_tier="", base_value=0)
