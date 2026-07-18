"""Shared mountain rise / ravine drop — Pass 1.4 + light contributors (tz_map_light_bake)."""

from __future__ import annotations

from app.dataModel.terrainMasks.worldTerrainMasks import (
    MountainsCategoryPolicy,
    RavinesCategoryPolicy,
)


def mountain_rise_amount(policy: MountainsCategoryPolicy, z_max: int) -> int:
    """``rise = round(z_max * rise_fraction_of_z_max)`` — SoT from MountainsCategoryPolicy."""
    return int(round(int(z_max) * float(policy.rise_fraction_of_z_max)))


def resolve_mountain_surface_z(
    base_z: int,
    *,
    z_min: int,
    z_max: int,
    policy: MountainsCategoryPolicy,
) -> int:
    """Clamp ``base + rise`` into ``[z_min, z_max]``."""
    rise = mountain_rise_amount(policy, z_max)
    return min(int(z_max), max(int(z_min), int(base_z) + rise))


def resolve_ravine_surface_z(
    base_z: int,
    *,
    z_min: int,
    policy: RavinesCategoryPolicy,
) -> int:
    """Lower surface by policy ``drop_z``, clamped to ``z_min``."""
    return max(int(z_min), int(base_z) - int(policy.drop_z))
