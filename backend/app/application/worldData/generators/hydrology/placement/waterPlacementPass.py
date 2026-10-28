"""Pre-1.4 common placement pass for declared water on the coarse snapshot (HY-12/3b)."""

import logging
from dataclasses import dataclass, replace

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
from app.dataModel.hydrology.declaredBasin import DeclaredBasin
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.placement import (
    PlacementBatch, PlacementBatchResult, PlacementPhase, ResolvedWaterPlacement,
)
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.planning.identity.planKey import OutputFingerprint
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.spatial.grid.coordinateTypes import FineZ, GridX, GridY, SurfaceGridCoord
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.application.planning.service.planFingerprints import output_fingerprint
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


def _auto_specificity(projected: WorldHydrology,
                      source: DeclaredBasin | DeclaredCoastline | DeclaredLake) -> int | None:
    if isinstance(source, DeclaredLake) or source.kind is BasinKind.LAKE:
        return projected.default_lakes.placement_specificity
    return projected.default_seas.placement_specificity


def legacy_surface_revision(heightmap: SurfaceHeightmap) -> OutputFingerprint:
    """PC-6W bridge until PC-9: fingerprint the actual uncached legacy surface.

    This narrow manifest is local to the legacy projection, not a plan binding.
    Providers always pass the output fingerprint of their exact terrain ref.
    """
    manifest = CanonicalSchemaManifest(entries=tuple(
        RegisteredTypeEntry(type_id=type_id, python_type=owner, kind=CanonicalTypeKind.RECORD)
        for type_id, owner in ((1, TerrainPlan), (2, GridBBox), (3, SurfaceGridCoord))))
    plan = TerrainPlan(bbox=heightmap.bbox, surface_z=tuple(
        (SurfaceGridCoord(GridX(x), GridY(y)), FineZ(z))
        for (x, y), z in sorted(heightmap.surface_z.items(), key=lambda item: (item[0][1], item[0][0]))))
    return output_fingerprint(plan, (), (), manifest)


def run_prepared_water_placement(pojo: WorldHydrology, context: WaterPlacementContext, *,
                                 fine_span: int, ctx: ResolveContext) -> WaterPlacementPassResult:
    """One baseline placement kernel for frozen planning and the legacy caller."""
    projected = project_declared_hydrology(pojo, fine_span, ctx=ctx, world_uid=context.world_uid)
    context = replace(context, auto_specificity={
        source.location_uid: _auto_specificity(projected, source)
        for source in [*projected.declared_basins, *projected.declared_coastlines, *projected.declared_lakes]
    })
    preparation = prepare_water_placements(projected, context, ctx=ctx)
    batch = PlacementBatch(world_uid=context.world_uid, snapshot_uid=context.snapshot_uid,
        snapshot_revision=context.snapshot_revision, phase=PlacementPhase.PRE_RELIEF,
        topology=context.topology, objects=preparation.objects, accepted=())
    batch_result = resolve_placements(batch, ctx=ctx)
    records = resolved_water_placements(preparation, batch_result)
    specs = tuple(basin_specs(preparation, records, projected))
    return WaterPlacementPassResult(preparation, batch_result, records, specs, context.topology)


def run_water_placement_pass(world: World, locations: list[NamedLocation], heightmap: SurfaceHeightmap,
                             *, ctx: ResolveContext | None = None) -> WaterPlacementPassResult | None:
    ctx = ctx or ResolveContext()
    pojo = hydrology(world)
    sources = [*pojo.declared_basins, *(c for c in pojo.declared_coastlines if c.is_water_source), *pojo.declared_lakes]
    if not is_hydrology_enabled(world) or not sources:
        return None
    topology = resolve_hydrology_topology(world, heightmap, locations=locations)
    map_cell = map_cell_fine_span(world)

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
    snapshot_uid = entity_uid(world.world_uid, UidKind.TERRAIN_SNAPSHOT, phase="pre_relief")
    context = WaterPlacementContext(
        world.world_uid, snapshot_uid, legacy_surface_revision(heightmap), topology, dict(heightmap.surface_z),
        world_z_min(world), anchors, location_subtypes, {}, {}, {}, {},
    )
    result = run_prepared_water_placement(pojo, context, fine_span=map_cell, ctx=ctx)
    logger.info(
        "water_placement_pass | world=%s prepared=%d resolved=%d unresolved=%d failures=%d",
        world.world_uid, len(result.preparation.objects), len(result.records),
        len(result.preparation.objects) - len(result.records), len(result.preparation.failures),
    )
    return result
