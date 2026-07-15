"""Upsample L0 parent light surface_z → fine meter heightmap (WP-PERF-22)."""

from __future__ import annotations

from app.application.worldData.generators.climate.math import world_seed
from app.application.worldData.generators.coordinates.worldTile import (
    meter_bbox_for_tile,
    world_meter_xy,
)
from app.application.worldData.generators.terrain.noise import cell_z_noise
from app.application.worldData.generators.terrain.worldMapSettings import world_z_max, world_z_min
from app.dataModel.worldPack.parentLightRefinePolicy import ParentLightRefinePolicy
from app.dataModel.worldPack.parentLightTile import ParentLightTile
from app.db.models.world import World


def _sample_z_nearest(parent: ParentLightTile, fx: float, fy: float) -> int:
    tx = min(parent.side - 1, max(0, int(fx)))
    ty = min(parent.side - 1, max(0, int(fy)))
    return parent.surface_z_at(tx, ty)


def _sample_z_bilinear(parent: ParentLightTile, fx: float, fy: float) -> float:
    x0 = min(parent.side - 1, max(0, int(fx)))
    y0 = min(parent.side - 1, max(0, int(fy)))
    x1 = min(parent.side - 1, x0 + 1)
    y1 = min(parent.side - 1, y0 + 1)
    tx = fx - x0
    ty = fy - y0
    z00 = float(parent.surface_z_at(x0, y0))
    z10 = float(parent.surface_z_at(x1, y0))
    z01 = float(parent.surface_z_at(x0, y1))
    z11 = float(parent.surface_z_at(x1, y1))
    z0 = z00 * (1.0 - tx) + z10 * tx
    z1 = z01 * (1.0 - tx) + z11 * tx
    return z0 * (1.0 - ty) + z1 * ty


def upsample_from_parent_light(
    parent: ParentLightTile,
    world: World,
    *,
    policy: ParentLightRefinePolicy | None = None,
) -> dict[tuple[int, int], int]:
    """Resample L0 ``surface_z`` to meter grid; detail noise; clamp to ±z_band."""
    pol = policy or ParentLightRefinePolicy.canonical_defaults()
    z_min = world_z_min(world)
    z_max = world_z_max(world)
    seed = world_seed(world)
    tile_m = parent.tile_m
    side = parent.side
    surface_z: dict[tuple[int, int], int] = {}

    for ly in range(tile_m):
        for lx in range(tile_m):
            xm, ym = world_meter_xy(parent.gx, parent.gy, lx, ly, tile_m)
            # Continuous light coords at cell center of meter.
            fx = (lx + 0.5) * side / tile_m
            fy = (ly + 0.5) * side / tile_m
            if pol.resample == "nearest":
                base = float(_sample_z_nearest(parent, fx, fy))
            else:
                base = _sample_z_bilinear(parent, fx, fy)
            base_i = int(round(base))
            noisy = cell_z_noise(
                seed, xm, ym, base_i, amplitude=pol.detail_noise_amplitude,
            )
            lo = base_i - pol.z_band
            hi = base_i + pol.z_band
            z = max(lo, min(hi, noisy))
            z = max(z_min, min(z_max, z))
            surface_z[(xm, ym)] = z

    return surface_z


def meter_bbox_for_parent(parent: ParentLightTile):
    return meter_bbox_for_tile(parent.gx, parent.gy, parent.tile_m)
