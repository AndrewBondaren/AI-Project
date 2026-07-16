"""Mountain autoresolve field — seed + climate bias (tz_map_light_bake).

Declare (geographic.mountain / peak) is applied by the mountain contributor via disk paint.
"""

from __future__ import annotations

from app.dataModel.terrainMasks.worldTerrainMasks import MountainsCategoryPolicy


def _ridge_unit(seed: int, xm: int, ym: int, ridge_cell_m: int) -> float:
    qx = xm // max(1, ridge_cell_m)
    qy = ym // max(1, ridge_cell_m)
    h = (seed ^ (qx * 73856093) ^ (qy * 19349663) ^ 0x9E3779B9) & 0xFFFFFFFF
    return (h % 1000) / 1000.0


def mountain_autoresolve_score(
    *,
    seed: int,
    xm: int,
    ym: int,
    surface_z: int,
    typical_elevation_z: int,
    policy: MountainsCategoryPolicy,
) -> float:
    ridge = _ridge_unit(seed, xm, ym, int(policy.ridge_cell_m))
    elev_bias = max(0, int(typical_elevation_z)) * float(policy.elevation_bias_weight)
    relief = (int(surface_z) - int(typical_elevation_z)) * float(policy.relief_weight)
    return ridge + elev_bias + relief


def is_mountain_autoresolve(
    *,
    seed: int,
    xm: int,
    ym: int,
    surface_z: int,
    typical_elevation_z: int,
    policy: MountainsCategoryPolicy,
) -> bool:
    if not policy.autoresolve:
        return False
    score = mountain_autoresolve_score(
        seed=seed,
        xm=xm,
        ym=ym,
        surface_z=surface_z,
        typical_elevation_z=typical_elevation_z,
        policy=policy,
    )
    return score >= float(policy.threshold)
