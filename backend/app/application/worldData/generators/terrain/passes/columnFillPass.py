from app.application.jsonValidation import terrain_scalars, terrain_system_keys
from app.application.worldData.generators.terrain.passes.gapAnalysisPass import n_base
from app.application.worldData.generators.terrain.worldMapSettings import world_z_min
from app.application.worldData.generators.terrain.terrainZ import (
    magma_terrain,
    subsurface_terrain_at_z,
    surface_terrain_at_z,
)
from app.application.worldData.generators.terrain.types import ColumnRect, SurfaceHeightmap
from app.db.models.mapCell import MapCell
from app.db.models.world import World


def _terrain_set(world: World) -> set[str]:
    return terrain_system_keys(world)


def _magma_thickness(world: World) -> int:
    t = terrain_scalars(world).magma_band_thickness
    if t is None or t <= 0:
        return 0
    return t


def run_column_fill(
    world: World,
    heightmap: SurfaceHeightmap,
    n_eff: dict[tuple[int, int], int],
    rect: ColumnRect | None = None,
) -> list[MapCell]:
    """Pass 2: fill solid columns (optional rect slice for chunking)."""
    terrain_set = _terrain_set(world)
    z_min       = world_z_min(world)
    magma_thick = _magma_thickness(world)
    use_magma   = magma_thick > 0 and bool(terrain_scalars(world).closed_planet_grid)

    x_lo = rect.x_min if rect else heightmap.bbox.x_min
    x_hi = rect.x_max if rect else heightmap.bbox.x_max
    y_lo = rect.y_min if rect else heightmap.bbox.y_min
    y_hi = rect.y_max if rect else heightmap.bbox.y_max

    cells: list[MapCell] = []

    for gy in range(y_lo, y_hi + 1):
        for gx in range(x_lo, x_hi + 1):
            key = (gx, gy)
            if key not in heightmap.surface_z:
                continue
            z_top    = heightmap.surface_z[key]
            depth    = n_eff.get(key, n_base(world))
            z_bottom = max(z_min, z_top - depth)

            for z in range(z_bottom, z_top + 1):
                terrain = (
                    surface_terrain_at_z(z, terrain_set)
                    if z == z_top
                    else subsurface_terrain_at_z(terrain_set)
                )
                cells.append(MapCell(
                    world_uid=world.world_uid,
                    x=gx,
                    y=gy,
                    z=z,
                    system_terrain=terrain,
                ))

            if use_magma:
                z_magma_top    = z_bottom - 1
                z_magma_bottom = z_magma_top - magma_thick + 1
                for z in range(z_magma_bottom, z_magma_top + 1):
                    if z < z_min:
                        continue
                    cells.append(MapCell(
                        world_uid=world.world_uid,
                        x=gx,
                        y=gy,
                        z=z,
                        system_terrain=magma_terrain(terrain_set),
                    ))

    return cells


def run_column_fill_single(
    world: World,
    heightmap: SurfaceHeightmap,
    n_eff: dict[tuple[int, int], int],
    gx: int,
    gy: int,
    z_lo: int,
    z_hi: int,
) -> list[MapCell]:
    """Fill one column between z_lo and z_hi (lazy z-slice)."""
    rect = ColumnRect(x_min=gx, x_max=gx, y_min=gy, y_max=gy)
    all_cells = run_column_fill(world, heightmap, n_eff, rect=rect)
    return [c for c in all_cells if z_lo <= c.z <= z_hi]
