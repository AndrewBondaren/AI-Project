"""Pre-1.4 common placement pass for declared water on the coarse snapshot (HY-12/3b)."""

import logging
from dataclasses import dataclass

from app.application.jsonValidation.resolve import ResolveContext
from app.application.jsonValidation.worldRow import hydrology
from app.application.worldData.generators.coordinates.convert import (
    fine_to_grid_xy, map_cell_fine_span,
)
from app.application.worldData.generators.hydrology.basinSpecFactory import basin_specs
from app.application.worldData.generators.hydrology.load.hydrologyLocations import (
    geographic_locations, geographic_subtype,
)
from app.application.worldData.generators.hydrology.load.loadHydrologyFromWorld import (
    is_hydrology_enabled,
)
from app.application.worldData.generators.hydrology.load.resolveHydrologyTopology import (
    resolve_hydrology_topology,
)
from app.application.worldData.generators.hydrology.placement.projectDeclaredHydrology import (
    project_declared_hydrology,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.application.worldData.generators.terrain.worldMapSettings import world_z_min
from app.application.worldData.placement import resolve_placements
from app.application.worldData.placement.adapters import (
    WaterPlacementContext, prepare_water_placements, resolved_water_placements,
)
from app.application.worldData.placement.adapters.waterTypes import WaterPlacementPreparation
from app.application.worldData.generators.terrain.reliefObjects.bathymetry import BasinSpec
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.placement import (
    PlacementBatch, PlacementBatchResult, PlacementPhase, ResolvedWaterPlacement,
)
from app.dataModel.topology.worldTopology import WorldTopology
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.ids import UidKind, entity_uid

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WaterPlacementPassResult:
    preparation: WaterPlacementPreparation
    batch_result: PlacementBatchResult
    records: tuple[ResolvedWaterPlacement, ...]
    basin_specs: tuple[BasinSpec, ...]
    topology: WorldTopology


def _auto_specificity(projected, source) -> int | None:
    if isinstance(source, DeclaredLake) or source.kind is BasinKind.LAKE:
        return projected.default_lakes.placement_specificity
    return projected.default_seas.placement_specificity


def run_water_placement_pass(world: World, locations: list[NamedLocation], heightmap: SurfaceHeightmap,
                             *, ctx: ResolveContext | None = None) -> WaterPlacementPassResult | None:
    ctx = ctx or ResolveContext()
    pojo = hydrology(world)
    sources = [*pojo.declared_basins, *pojo.declared_coastlines, *pojo.declared_lakes]
    if not is_hydrology_enabled(world) or not sources:
        return None
    topology = resolve_hydrology_topology(world, heightmap, locations=locations)
    map_cell = map_cell_fine_span(world)
    projected = project_declared_hydrology(pojo, map_cell, ctx=ctx, world_uid=world.world_uid)

    anchors = {}
    location_subtypes = {}
    for loc in geographic_locations(locations):
        if loc.map_x is not None and loc.map_y is not None:
            canonical = topology.canonicalize(*fine_to_grid_xy(loc.map_x, loc.map_y, map_cell))
            if canonical is not None:
                anchors[loc.location_uid] = canonical
        subtype = geographic_subtype(loc)
        if subtype is not None:
            location_subtypes[loc.location_uid] = subtype
    auto_specificity = {
        source.location_uid: _auto_specificity(projected, source)
        for source in [*projected.declared_basins, *projected.declared_coastlines,
                       *projected.declared_lakes]
    }
    snapshot_uid = entity_uid(world.world_uid, UidKind.TERRAIN_SNAPSHOT, phase="pre_relief")
    context = WaterPlacementContext(
        world.world_uid, snapshot_uid, topology, dict(heightmap.surface_z),
        world_z_min(world), anchors, location_subtypes, auto_specificity, {}, {}, {},
    )
    preparation = prepare_water_placements(projected, context, ctx=ctx)
    batch = PlacementBatch(world_uid=world.world_uid, snapshot_uid=snapshot_uid,
                           phase=PlacementPhase.PRE_RELIEF, topology=topology,
                           objects=preparation.objects, accepted=())
    batch_result = resolve_placements(batch, ctx=ctx)
    records = resolved_water_placements(preparation, batch_result)
    specs = tuple(basin_specs(preparation, records, projected))
    logger.info(
        "water_placement_pass | world=%s prepared=%d resolved=%d unresolved=%d failures=%d",
        world.world_uid, len(preparation.objects), len(records),
        len(preparation.objects) - len(records), len(preparation.failures),
    )
    return WaterPlacementPassResult(preparation, batch_result, records, specs, topology)
