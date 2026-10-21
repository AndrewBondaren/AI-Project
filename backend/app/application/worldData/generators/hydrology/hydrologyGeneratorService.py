"""Hydrology facade: post-relief bodies, rivers, optional landforms."""

from collections.abc import Sequence
import logging

from app.application.jsonValidation.resolve import ResolveContext
from app.application.jsonValidation.worldRow import hydrology
from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.hydrology.basins.coastalLandformClassifier import classify_coastal_landforms
from app.application.worldData.generators.hydrology.load.buildHydrologyMasterInput import build_hydrology_master_input
from app.application.worldData.generators.hydrology.load.resolveHydrologyTopology import resolve_hydrology_topology
from app.application.worldData.generators.hydrology.riverNetworkAssembler import assemble_rivers
from app.application.worldData.generators.hydrology.types import (
    HydrologyMasterInput, HydrologyResult, HydrologyScope, resolve_scopes,
)
from app.application.worldData.generators.hydrology.water.waterDiagnostics import water_issue
from app.application.worldData.generators.hydrology.waterBodyAssembler import assemble_water_bodies
from app.application.worldData.generators.terrain.reliefObjects.bathymetry import BasinSpec
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.topology.worldTopology import WorldTopology
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.ids.waterSystemIdentity import initial_water_change_uid

logger = logging.getLogger(__name__)


def _merge_bbox(a: GridBBox | None, b: GridBBox | None) -> GridBBox | None:
    if a is None:
        return b
    if b is None:
        return a
    return GridBBox(min(a.x_min, b.x_min), max(a.x_max, b.x_max),
                    min(a.y_min, b.y_min), max(a.y_max, b.y_max))


class HydrologyGeneratorService:
    """Pure bootstrap/preview facade; body water never writes terrain z.

    Callers pass the very specs used in Pass 1.4. Stateful W/L operations must
    supply their durable change_uid; the default is a replayable first bake.
    River-bed elevation is applied through the relief writer after planning.
    """

    def apply(self, world: World, locations: list[NamedLocation], heightmap: SurfaceHeightmap, *,
              nodes: list[ConnectionNode] | None = None, edges: list[ConnectionEdge] | None = None,
              scopes: frozenset[HydrologyScope] | None = None,
              master: HydrologyMasterInput | None = None,
              basin_specs: Sequence[BasinSpec] | None = None,
              topology: WorldTopology | None = None, change_uid: str | None = None,
              ctx: ResolveContext | None = None) -> HydrologyResult:
        inp = master or build_hydrology_master_input(world, locations, nodes or [], edges or [], scopes=scopes)
        result = HydrologyResult(heightmap=heightmap)
        if not inp.hydrology_enabled:
            return result
        ctx = ctx or ResolveContext()
        active = resolve_scopes(inp.scopes)
        topology = topology if topology is not None else resolve_hydrology_topology(
            world, heightmap, locations=locations)
        policy = hydrology(world)
        seas = bool(active & {HydrologyScope.COASTAL_SEA, HydrologyScope.OPEN_OCEAN})
        lakes = HydrologyScope.LAKES in active
        if seas or lakes:
            if basin_specs is None and (policy.declared_basins or policy.declared_coastlines or policy.declared_lakes):
                water_issue(ctx, world.world_uid, "declared water requires resolved post-carve BasinSpec input",
                            "WATER_PLACEMENT_REQUIRED")
            specs = [spec for spec in (basin_specs or ())
                     if (lakes and policy.default_lakes.enabled if spec.kind is BasinKind.LAKE
                         else seas and policy.default_seas.enabled)]
            water = assemble_water_bodies(
                heightmap, specs, topology,
                policy, change_uid=change_uid if change_uid is not None else initial_water_change_uid(world.world_uid),
                auto_seas=bool(seas and policy.default_seas.enabled and (
                    policy.default_seas.autoresolve_coastal_sea or policy.default_seas.autoresolve_open_ocean)),
                auto_lakes=bool(lakes and policy.default_lakes.enabled and policy.default_lakes.autoresolve), ctx=ctx,
                allowed_kinds=frozenset(
                    ([BasinKind.LAKE] if lakes and policy.default_lakes.enabled else [])
                    + ([BasinKind.SEA, BasinKind.OCEAN, BasinKind.INLAND_SEA]
                       if seas and policy.default_seas.enabled else [])),
            )
            result.cell_index.by_cell.update(water.materialized.by_cell)
            result.water_bodies = water.materialized.bodies
            result.physical_unions = water.physical_unions
            result.water_areas = water.materialized.areas
            result.water_floors = water.materialized.floors
            if result.cell_index.by_cell:
                xs, ys = zip(*result.cell_index.by_cell)
                result.dirty_bbox = GridBBox(min(xs), max(xs), min(ys), max(ys))
        if HydrologyScope.RIVERS in active:
            rivers = assemble_rivers(world, heightmap, inp, occupied=result.cell_index.by_cell,
                                     locations=locations, topology=topology,
                                     water_bodies=result.water_bodies, ctx=ctx)
            result.cell_index.by_cell.update(rivers.by_cell)
            result.river_segments = rivers.segments
            result.river_diagnostics = rivers.diagnostics
            result.river_drainage_links = rivers.drainage_links
            result.waterfall_drops = rivers.drops
            result.dirty_bbox = _merge_bbox(result.dirty_bbox, rivers.dirty_bbox)
        if HydrologyScope.LANDFORMS in active:
            result.landforms = classify_coastal_landforms(inp)
        logger.info("HydrologyGeneratorService | world=%s scopes=%s cells=%d bodies=%d unions=%d",
                    world.world_uid, sorted(s.value for s in active), result.cells_modified,
                    len(result.water_bodies), len(result.physical_unions))
        return result
