from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.application.worldData.generators.terrain.worldMapSettings import n_base
from app.db.models.world import World


def _neighbors4(gx: int, gy: int) -> list[tuple[int, int]]:
    return [(gx + 1, gy), (gx - 1, gy), (gx, gy + 1), (gx, gy - 1)]


def run_gap_analysis(
    world: World,
    heightmap: SurfaceHeightmap,
) -> dict[tuple[int, int], int]:
    """Compute N_eff per column: max(N_base, Δ_cliff)."""
    base   = n_base(world)
    n_eff: dict[tuple[int, int], int] = {}

    for (gx, gy), z_top in heightmap.surface_z.items():
        neighbor_zs = [
            heightmap.surface_z[n]
            for n in _neighbors4(gx, gy)
            if n in heightmap.surface_z
        ]
        if neighbor_zs:
            delta_cliff = max(0, z_top - min(neighbor_zs))
        else:
            delta_cliff = 0
        n_eff[(gx, gy)] = max(base, delta_cliff)

    return n_eff
