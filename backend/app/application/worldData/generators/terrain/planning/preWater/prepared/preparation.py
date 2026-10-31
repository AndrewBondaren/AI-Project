"""Prepare immutable natural geometry once, independently of requested windows."""
from itertools import groupby

from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.coordinates.light.grid import fine_to_macro_local
from app.application.worldData.generators.terrain.hills.hillLayout import build_hill_layout
from app.application.worldData.generators.terrain.hills.hillSelection import prepare_hills
from app.application.worldData.generators.terrain.planning.preWater.terrainBaseJob import PreWaterTerrainJob
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult, PlanEnvelope
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnosticDisposition
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY, LightCellRef
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
from app.dataModel.terrain.planning.natural.preparedTerrain import NaturalTerrainTile, PreparedNaturalTerrain
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput
from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import SurfaceSupportInput
from app.dataModel.topology.worldTopology import Coord


def _protected_spans(cells: list[Coord]) -> tuple[CoverageSpan, ...]:
    spans = []
    for y, row in groupby(sorted(cells, key=lambda c: (c[1], c[0])), key=lambda c: c[1]):
        start = end = None
        for x, _ in row:
            if end is not None and x != end:
                assert start is not None
                spans.append(CoverageSpan(y=FineY(y), x0=FineX(start), x1=FineX(end)))
                start = None
            if start is None:
                start = x
            end = x+1
        assert start is not None and end is not None
        spans.append(CoverageSpan(y=FineY(y), x0=FineX(start), x1=FineX(end)))
    return tuple(spans)


class NaturalPreparationJob:
    def prepare(self, world_uid: EntityUid, base: TerrainBaseInput, relief: ReliefPlanInput,
                support: SurfaceSupportInput, climate: PlanEnvelope[ClimateBasePlan],
                terrain: PlanEnvelope[TerrainPlan], control: PlanBuildControl) -> PlanBuildResult[PreparedNaturalTerrain]:
        control.raise_if_shutdown()
        errors = tuple(d.issue for e in (climate, terrain) for d in e.diagnostics
                       if d.disposition is PlanDiagnosticDisposition.ERROR)
        if errors:
            raise PlanBuildFailure(errors)
        job = PreWaterTerrainJob(world_uid, base, relief, support, climate, terrain, control)
        span = base.grid.fine_span
        protected: dict[Coord, list[Coord]] = {}
        for cell in job.protected:
            protected.setdefault((cell[0]//span, cell[1]//span), []).append(cell)
        tiles = []
        for cell, _ in terrain.payload.surface_z:
            control.raise_if_shutdown()
            gx, gy = cell.gx, cell.gy
            hosts: dict[Coord, str] = {c: key for c, key in job.hosts.project_tile(gx, gy)}
            protection = protected.get((gx, gy), [])
            excluded = set(protection)
            excluded.update(c for c in hosts if LightCellRef(*fine_to_macro_local(*c, job.scale)) in job.ravines)
            hills = prepare_hills(GridBBox(gx*span, (gx+1)*span-1, gy*span, (gy+1)*span-1),
                hosts, excluded, registry=job.hosts.sources.registry, seed=base.seed)
            tiles.append(NaturalTerrainTile(gx=gx, gy=gy, protected_spans=_protected_spans(protection),
                                           hills=build_hill_layout(hills)))
        control.raise_if_shutdown()
        return PlanBuildResult[PreparedNaturalTerrain](payload=PreparedNaturalTerrain(
            base=base, topology=job.topology, refine_policy=support.refine_policy,
            mountain_layout=job.layout, light=job.light, tiles=tuple(tiles)), diagnostics=())
