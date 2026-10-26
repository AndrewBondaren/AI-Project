"""Fine river planning over resolved water; relief remains the elevation writer."""

from collections.abc import Sequence
from itertools import chain

from app.application.jsonValidation.resolve import ResolveContext
from app.application.jsonValidation.worldRow import hydrology
from app.application.worldData.generators.coordinates.space import CoordinateSpace
from app.application.worldData.generators.coordinates.worldTile import expand_coarse_hydro_to_tile, fine_bbox_for_tile
from app.application.worldData.generators.hydrology.load.loadDeclaredHydrology import load_declared_hydrology
from app.application.worldData.generators.hydrology.load.resolveRiverTypeClassify import resolve_river_type_classify
from app.application.worldData.generators.hydrology.rivers.riverBedProfile import river_bed_roles
from app.application.worldData.generators.hydrology.rivers.riverPrepare import prepare_river_requests
from app.application.worldData.generators.hydrology.rivers.riverRouteDiagnostics import emit_river_diagnostic
from app.application.worldData.generators.hydrology.rivers.riverRouteRequests import declared_river_requests
from app.application.worldData.generators.hydrology.shore.fineRiverSampling import sample_fine_river_input
from app.application.worldData.generators.terrain.reliefObjects.riverBed import apply_river_bed_z
from app.application.worldData.generators.terrain.worldMapSettings import world_z_min
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.topology.worldTopology import Coord, WorldTopology
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def apply_declared_fine_river_carves(
    world: World, locations: list[NamedLocation], base_surface_z: dict[Coord, int], *, topology: WorldTopology,
    base_space: CoordinateSpace = CoordinateSpace.WORLD_FINE_GRID,
    coarse_hydro: dict[Coord, MapCellHydrology] | None = None,
    fine_hydro: dict[Coord, MapCellHydrology] | None = None,
    water_bodies: Sequence[WaterBody] = (), ctx: ResolveContext | None = None,
) -> tuple[dict[Coord, MapCellHydrology], dict[Coord, int]]:
    """Sample before planning; atomically prepare profiles, apply once, then publish roles."""
    if not isinstance(topology, WorldTopology):
        raise TypeError("fine rivers require an explicit WorldTopology")
    if base_space not in (CoordinateSpace.WORLD_FINE_GRID, CoordinateSpace.WORLD_SURFACE_GRID):
        raise ValueError(f"unsupported river base space: {base_space}")
    if (base_space is CoordinateSpace.WORLD_FINE_GRID and coarse_hydro) or (
            base_space is CoordinateSpace.WORLD_SURFACE_GRID and fine_hydro):
        raise ValueError("resolved river input hydrology must match base_space")
    ctx = ctx if ctx is not None else ResolveContext()
    policy, classify = hydrology(world).default_rivers, resolve_river_type_classify(world)
    loaded = load_declared_hydrology(world, locations)
    sampling = sample_fine_river_input(world, loaded, locations, base_surface_z, topology, base_space,
                                      coarse_hydro or {}, fine_hydro or {}, policy)
    hm = sampling.heightmap
    requests = declared_river_requests(world, hm, loaded.river_edges, loaded.river_intents, locations,
        sampling.occupied, classify, topology, space=CoordinateSpace.WORLD_FINE_GRID)
    requests = sampling.sample_requests(requests, classify)
    jobs = prepare_river_requests(world, hm, requests, dict(sampling.occupied), topology, policy,
        water_bodies, ctx, world_z_min(world), space=CoordinateSpace.WORLD_FINE_GRID)
    hm = sampling.output_heightmap(cell for segments in chain(
        (request.segments for request in requests), (job.segments for job in jobs))
        for segment in segments for cell in segment.polyline_cells)
    apply_river_bed_z(hm, tuple(spec for job in jobs for spec in job.specs))
    merged = {}
    for job in jobs:
        for segment, spec in zip(job.segments, job.specs, strict=True):
            merged.update(river_bed_roles(segment, spec, drainage=job.drainage))
        for diagnostic in job.diagnostics:
            emit_river_diagnostic(ctx, diagnostic)
    return merged, hm.surface_z


def merge_fine_hydro_for_tile(
    tile_gx: int,
    tile_gy: int,
    map_cell: int,
    coarse_hydro: dict[tuple[int, int], MapCellHydrology],
    sparse_fine_hydro: dict[tuple[int, int], MapCellHydrology],
) -> dict[tuple[int, int], MapCellHydrology]:
    merged: dict[tuple[int, int], MapCellHydrology] = {}
    merged.update(expand_coarse_hydro_to_tile(coarse_hydro, tile_gx, tile_gy, map_cell))

    fine_bbox = fine_bbox_for_tile(tile_gx, tile_gy, map_cell)
    for (xm, ym), entry in sparse_fine_hydro.items():
        if (
            fine_bbox.x_min <= xm <= fine_bbox.x_max
            and fine_bbox.y_min <= ym <= fine_bbox.y_max
        ):
            merged[(xm, ym)] = entry

    return merged
