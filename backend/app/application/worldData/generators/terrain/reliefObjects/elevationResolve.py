"""Shared mountain rise / ravine drop — Pass 1.4 + light (tz_map_light_bake)."""

from __future__ import annotations

from app.dataModel.terrainMasks.mountain.enums import MountainKind, mountain_kind_profile
from app.dataModel.terrainMasks.worldTerrainMasks import RavinesCategoryPolicy


def mountain_rise_amount(kind: MountainKind, z_max: int) -> int:
    """``rise = round(z_max * kind.profile.rise_fraction_of_z_max)``."""
    fraction = float(mountain_kind_profile(kind).rise_fraction_of_z_max)
    return int(round(int(z_max) * fraction))


def resolve_mountain_surface_z(
    base_z: int,
    *,
    z_min: int,
    z_max: int,
    kind: MountainKind,
    side_fraction: float = 1.0,
) -> int:
    """``z = base + rise * side_fraction``, clamped to ``[z_min, z_max]``."""
    rise = mountain_rise_amount(kind, z_max)
    frac = max(0.0, min(1.0, float(side_fraction)))
    return min(int(z_max), max(int(z_min), int(base_z) + int(round(rise * frac))))


def resolve_ravine_surface_z(
    base_z: int,
    *,
    z_min: int,
    policy: RavinesCategoryPolicy,
) -> int:
    """Lower surface by policy ``drop_z``, clamped to ``z_min``."""
    return max(int(z_min), int(base_z) - int(policy.drop_z))
