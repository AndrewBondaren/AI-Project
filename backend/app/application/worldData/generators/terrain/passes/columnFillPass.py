from app.application.jsonValidation import terrain_masks, terrain_scalars, terrain_system_keys
from app.application.worldData.generators.terrain.passes.gapAnalysisPass import n_base
from app.application.worldData.generators.hydrology.shore.shoreProfile import (
    apply_shore_surface,
    shore_terrain_material,
)
from app.application.worldData.generators.terrain.worldMapSettings import world_z_min
from app.application.worldData.generators.terrain.resolveWorldMapTerrain import (
    default_surface_terrain,
)
from app.application.worldData.generators.terrain.terrainZ import (
    magma_terrain,
    subsurface_terrain_at_z,
    surface_biome_terrain,
)
from app.application.worldData.generators.terrain.types import ColumnRect, SurfaceHeightmap
from app.dataModel.climate.worldClimateScalars import WorldClimateScalars
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology, dump_cell_hydrology
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
    hydrology_by_cell: dict[tuple[int, int], MapCellHydrology] | None = None,
    surface_terrain: dict[tuple[int, int], str] | None = None,
) -> list[MapCell]:
    """Pass 2: fill solid columns (optional rect slice for chunking).

    Pack L2 refine: pass ``surface_terrain`` from parent light (mask carry).
    Legacy path without map: climate landcover via ``surface_biome_terrain``.
    """
    terrain_set = _terrain_set(world)
    z_min       = world_z_min(world)
    magma_thick = _magma_thickness(world)
    use_magma   = magma_thick > 0 and bool(terrain_scalars(world).closed_planet_grid)
    shore_terrain, shore_material = shore_terrain_material(world)
    default_zone = WorldClimateScalars.canonical_defaults().default_climate_zone
    masks = terrain_masks(world)
    plains_fallback = default_surface_terrain(world)

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
                if z == z_top:
                    if surface_terrain is not None:
                        terrain = surface_terrain.get(key) or plains_fallback
                    else:
                        terrain = surface_biome_terrain(
                            terrain_set,
                            system_climate_zone=default_zone,
                            masks=masks,
                        )
                else:
                    terrain = subsurface_terrain_at_z(terrain_set)
                hydrology_entry = hydrology_by_cell.get(key) if hydrology_by_cell else None
                hydrology_wire = None
                material = None
                if z == z_top and hydrology_entry is not None:
                    hydrology_wire = dump_cell_hydrology(hydrology_entry)
                    terrain = apply_shore_surface(
                        hydrology_entry.role,
                        z,
                        terrain_set,
                        terrain,
                        shore_terrain=shore_terrain,
                    )
                    if hydrology_entry.role == HydrologyCellRole.SHORE:
                        material = shore_material
                    elif (
                        hydrology_entry.role == HydrologyCellRole.RIVER_BED
                        and "liquid_body" in terrain_set
                    ):
                        terrain = "liquid_body"
                cells.append(MapCell(
                    world_uid=world.world_uid,
                    x=gx,
                    y=gy,
                    z=z,
                    system_terrain=terrain,
                    system_material=material,
                    hydrology=hydrology_wire,
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
