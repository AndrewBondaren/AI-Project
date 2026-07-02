"""Tier-2 anchor influence radius — tz_climate.md § Pole field / local modifiers."""

from __future__ import annotations

from app.dataModel.climate.worldClimateScalars import WorldClimateScalars

LOCAL_INFLUENCE_BLEND_OUTER = 0.2


def local_influence_fraction(world_value: float | None) -> float:
    if world_value is not None:
        return float(world_value)
    return float(WorldClimateScalars.canonical_defaults().climate_local_influence_fraction)
