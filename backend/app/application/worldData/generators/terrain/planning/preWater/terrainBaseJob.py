"""Terrain-owned natural fine surface and protected mountain geometry."""

from collections.abc import Iterable
from itertools import chain, groupby

from app.application.jsonValidation.resolve import ResolveContext
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.coordinates.light.grid import fine_to_macro_local
from app.application.worldData.generators.terrain.hills.hillPlacement import place_resolved_hills
from app.application.worldData.generators.terrain.hills.hillLayout import build_hill_layout
from app.application.worldData.generators.terrain.hills.hillSelection import prepare_hills
from app.application.worldData.generators.terrain.landcover.planning.preWaterHillHosts import PreWaterHillHostJob
from app.application.worldData.generators.terrain.mountains.formPipeline import coarse_footprint_for_entry
from app.application.worldData.generators.terrain.passes.lightSurfaceRefine import refine_light_surface
from app.application.worldData.generators.terrain.relief.planning.naturalRelief import mountain_layout, light_relief
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult, PlanEnvelope
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnosticDisposition
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY, LightCellRef
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.spatial.grid.lightGridScale import LightGridScale
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.planning.natural.preparedTerrain import NaturalTerrainTile, PreparedNaturalTerrain
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan, RegionCoverage
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput
from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import SurfaceSupportInput
from app.dataModel.terrain.worldTerrainRegistry import TerrainKey
from app.dataModel.topology.fineTopology import fine_topology
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


class PreWaterTerrainJob:
    """Evaluate one captured natural recipe; tile-complete hills precede request clipping."""

    def __init__(self, world_uid: EntityUid, base_input: TerrainBaseInput, relief_input: ReliefPlanInput,
                 support_input: SurfaceSupportInput, climate_base: PlanEnvelope[ClimateBasePlan],
                 terrain_base: PlanEnvelope[TerrainPlan], control: PlanBuildControl):
        control.raise_if_shutdown()
        if not (base_input.seed == relief_input.seed == support_input.seed
                and base_input.grid == relief_input.grid == support_input.grid
                and base_input.z_min == relief_input.z_min and base_input.z_max == relief_input.z_max
                and base_input.bbox == terrain_base.payload.bbox
                and relief_input.masks_enabled == support_input.masks_enabled):
            raise ValueError("pre-water terrain requires coherent captured seed/grid/z bounds/extent/mask gate")
        if any(not base_input.z_min <= z <= base_input.z_max for _, z in terrain_base.payload.surface_z):
            raise ValueError("terrain base elevations exceed captured world z bounds")
        self.world_uid, self.base, self.control = world_uid, base_input, control
        self.support = support_input
        self.hosts = PreWaterHillHostJob(world_uid, support_input, climate_base, terrain_base)
        self.hill_policies = dict(self.hosts.resolved_hill_policies())
        self.topology = fine_topology(support_input.topology, base_input.grid.fine_span)
        self.scale = LightGridScale.from_tile(base_input.grid.fine_span, base_input.grid.light_side)
        ctx = ResolveContext(collect_only=True)
        layout = mountain_layout(relief_input, terrain_base.payload, climate_base.payload, world_uid, ctx, control)
        if ctx.errors:
            raise PlanBuildFailure(tuple(ctx.errors))
        light = light_relief(relief_input, terrain_base.payload, layout, self.scale, control)
        self.layout, self.light = layout, light
        self.light_z = dict(light.base_surface_z)
        self.light_z.update((effect.cell, effect.surface_z) for effect in light.mountain_cells)
        self.light_z.update((effect.cell, effect.surface_z) for effect in light.ravine_cells)
        self.ravines = frozenset(effect.cell for effect in light.ravine_cells)
        protected: set[Coord] = set()
        for entry in layout.entries:
            control.raise_if_shutdown()
            # A fine cell is one metre. Reuse the form/side kernels at that resolution,
            # rather than inflating a projected light-cell or water mask into protection.
            for point in coarse_footprint_for_entry(entry, cell_m=1, light_span=1.0):
                canonical = self.topology.canonicalize(*point)
                if canonical is not None:
                    protected.add(canonical)
        self.protected = frozenset(protected)

    @classmethod
    def prepare_revision(cls, world_uid: EntityUid, base: TerrainBaseInput, relief: ReliefPlanInput,
                         support: SurfaceSupportInput, climate: PlanEnvelope[ClimateBasePlan],
                         terrain: PlanEnvelope[TerrainPlan], control: PlanBuildControl) -> PlanBuildResult[PreparedNaturalTerrain]:
        """Public ready-data operation; consumers do not inspect an executing job."""
        control.raise_if_shutdown()
        errors = tuple(d.issue for envelope in (climate, terrain) for d in envelope.diagnostics
                       if d.disposition is PlanDiagnosticDisposition.ERROR)
        if errors:
            raise PlanBuildFailure(errors)
        return cls(world_uid, base, relief, support, climate, terrain, control)._prepare_revision(terrain.payload)

    def _hill_exclusions(self, cells: Iterable[Coord], protected: Iterable[Coord]) -> frozenset[Coord]:
        """One admission rule; callers retain their original candidate/protection scopes."""
        return frozenset(chain(protected, (cell for cell in cells
            if LightCellRef(*fine_to_macro_local(*cell, self.scale)) in self.ravines)))

    def _prepare_revision(self, terrain: TerrainPlan) -> PlanBuildResult[PreparedNaturalTerrain]:
        span = self.base.grid.fine_span
        protected: dict[Coord, list[Coord]] = {}
        for cell in self.protected:
            protected.setdefault((cell[0]//span, cell[1]//span), []).append(cell)
        tiles = []
        for cell, _ in terrain.surface_z:
            self.control.raise_if_shutdown()
            gx, gy = cell.gx, cell.gy
            hosts: dict[Coord, TerrainKey] = {c: key for c, key in self.hosts.project_tile(gx, gy)}
            protection = protected.get((gx, gy), [])
            excluded = self._hill_exclusions(hosts, protection)
            hills = prepare_hills(GridBBox(gx*span, (gx+1)*span-1, gy*span, (gy+1)*span-1),
                hosts, excluded, hill_policies=self.hill_policies, seed=self.base.seed)
            tiles.append(NaturalTerrainTile(gx=gx, gy=gy, protected_spans=_protected_spans(protection),
                                           hills=build_hill_layout(hills)))
        self.control.raise_if_shutdown()
        return PlanBuildResult[PreparedNaturalTerrain](payload=PreparedNaturalTerrain(
            base=self.base, topology=self.topology, refine_policy=self.support.refine_policy,
            mountain_layout=self.layout, light=self.light, tiles=tuple(tiles)), diagnostics=())

    def _tile(self, gx: int, gy: int, region_uid: EntityUid) -> dict[Coord, int]:
        self.control.raise_if_shutdown()
        span = self.base.grid.fine_span
        coverage = RegionCoverage(region_uid=region_uid, spans=tuple(
            CoverageSpan(y=FineY(y), x0=FineX(gx * span), x1=FineX((gx + 1) * span))
            for y in range(gy * span, (gy + 1) * span)))
        hosts: dict[Coord, TerrainKey] = {cell: key for cell, key in self.hosts.project(coverage)}
        surface = refine_light_surface(gx, gy, self.base.grid,
            lambda tx, ty: self.light_z[LightCellRef(gx, gy, tx, ty)],
            seed=self.base.seed, z_min=self.base.z_min, z_max=self.base.z_max, policy=self.support.refine_policy)
        excluded = self._hill_exclusions(surface, self.protected)
        place_resolved_hills(surface, hosts, excluded, hill_policies=self.hill_policies,
                    seed=self.base.seed, z_min=self.base.z_min, z_max=self.base.z_max)
        self.control.raise_if_shutdown()
        return surface

    def prepare(self, cells: RegionCoverage) -> tuple[SurfaceHeightmap, frozenset[Coord]]:
        if not cells.spans:
            raise ValueError("pre-water terrain requires nonempty coverage")
        bounds, span = self.topology.bounds, self.base.grid.fine_span
        tiles: set[Coord] = set()
        for row in cells.spans:
            if not bounds.contains(row.x0, row.y) or not bounds.contains(row.x1 - 1, row.y):
                raise ValueError("pre-water terrain requires canonical fine coverage within captured topology")
            tiles.update((gx, row.y // span) for gx in range(row.x0 // span, (row.x1 - 1) // span + 1))
        surfaces = {tile: self._tile(*tile, cells.region_uid) for tile in sorted(tiles, key=lambda c: (c[1], c[0]))}
        surface: dict[Coord, int] = {(x, row.y): surfaces[(x // span, row.y // span)][(x, row.y)]
                   for row in cells.spans for x in range(row.x0, row.x1)}
        bbox = GridBBox(x_min=min(row.x0 for row in cells.spans), x_max=max(row.x1 - 1 for row in cells.spans),
                        y_min=cells.spans[0].y, y_max=cells.spans[-1].y)
        self.control.raise_if_shutdown()
        return SurfaceHeightmap(self.world_uid, bbox, surface), self.protected.intersection(surface)
