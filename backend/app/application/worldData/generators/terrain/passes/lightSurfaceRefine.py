"""One light-to-fine height kernel for baked parents and pre-water recipes."""

from collections.abc import Callable

from app.application.worldData.generators.coordinates.worldTile import world_fine_xy
from app.application.worldData.generators.terrain.noise import cell_z_noise
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.worldPack.bake.parentLightRefinePolicy import ParentLightRefinePolicy


def _sample_z_nearest(side: int, z_at: Callable[[int, int], int], fx: float, fy: float) -> int:
    tx = min(side - 1, max(0, int(fx)))
    ty = min(side - 1, max(0, int(fy)))
    return z_at(tx, ty)


def _sample_z_bilinear(side: int, z_at: Callable[[int, int], int], fx: float, fy: float) -> float:
    x0 = min(side - 1, max(0, int(fx)))
    y0 = min(side - 1, max(0, int(fy)))
    x1 = min(side - 1, x0 + 1)
    y1 = min(side - 1, y0 + 1)
    tx = fx - x0
    ty = fy - y0
    z00 = float(z_at(x0, y0))
    z10 = float(z_at(x1, y0))
    z01 = float(z_at(x0, y1))
    z11 = float(z_at(x1, y1))
    z0 = z00 * (1.0 - tx) + z10 * tx
    z1 = z01 * (1.0 - tx) + z11 * tx
    return z0 * (1.0 - ty) + z1 * ty


def refine_light_surface(gx: int, gy: int, grid: SurfaceGridSettings,
                         z_at: Callable[[int, int], int], *, seed: int, z_min: int, z_max: int,
                         policy: ParentLightRefinePolicy) -> dict[tuple[int, int], int]:
    """Refine a complete tile; source ownership and stage belong to the caller."""
    tile_macro, side = grid.fine_span, grid.light_side
    surface_z: dict[tuple[int, int], int] = {}

    for ly in range(tile_macro):
        for lx in range(tile_macro):
            xm, ym = world_fine_xy(gx, gy, lx, ly, tile_macro)
            # Continuous light coords at cell center of meter.
            fx = (lx + 0.5) * side / tile_macro
            fy = (ly + 0.5) * side / tile_macro
            if policy.resample == "nearest":
                base = float(_sample_z_nearest(side, z_at, fx, fy))
            else:
                base = _sample_z_bilinear(side, z_at, fx, fy)
            base_i = int(round(base))
            noisy = cell_z_noise(
                seed, xm, ym, base_i, amplitude=policy.detail_noise_amplitude,
            )
            lo = base_i - policy.z_band
            hi = base_i + policy.z_band
            z = max(lo, min(hi, noisy))
            z = max(z_min, min(z_max, z))
            surface_z[(xm, ym)] = z

    return surface_z