"""Whole-scope terrain/region inputs, with different coarse/fine/light scales."""

from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageAllocation
from app.dataModel.terrain.designedWater.fields.field import ContinentalField
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan, RegionCoverage
from app.dataModel.terrain.regions.terrainRegionExtent import TerrainRegionExtent
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology
from tests.geo1.contracts.strategies.fixtures import inputs, draft_for


def procedural_case(*, strategy=Strategy.CONTINENTAL_NOISE, allocated=8, span=2,
                    bounds=None, coverage=None, mode=WorldTopologyMode.WRAPPED, values=None):
    base = inputs(strategy)
    topology = WorldTopology(mode=mode, bounds=bounds or WorldBounds(x_min=0, x_max=1, y_min=0, y_max=1))
    bounds = topology.bounds
    grid = SurfaceGridSettings(fine_span=span, light_side=3)
    fine_bounds = fine_topology(topology, span).bounds
    if coverage is None:
        coverage = RegionCoverage(region_uid="region", spans=tuple(
            CoverageSpan(y=y, x0=fine_bounds.x_min, x1=fine_bounds.x_max + 1)
            for y in range(fine_bounds.y_min, fine_bounds.y_max + 1)))
    area = sum(s.x1 - s.x0 for s in coverage.spans)
    coords = tuple(SurfaceGridCoord(x, y) for y in range(bounds.y_min, bounds.y_max + 1)
                   for x in range(bounds.x_min, bounds.x_max + 1))
    surface = TerrainPlan(bbox=GridBBox(bounds.x_min, bounds.x_max, bounds.y_min, bounds.y_max),
        surface_z=tuple((c, 3) for c in coords))
    recipe = base.field_policy.model_copy(update={"topology": fine_topology(topology, span)})
    input = type(base).model_validate(base.model_copy(update=dict(
        topology=topology, grid=grid, field_policy=recipe,
        budget=BodyCoverageAllocation(source_uid="source", generation_region_uid="region",
            requested_fine2=area, allocated_fine2=allocated),
        region=TerrainRegionExtent(region_uid="region", generation_area_fine2=area), region_coverage=coverage,
        pre_hydrology=PlanEnvelope[TerrainPlan](ref=base.pre_hydrology_ref, payload=surface,
            dependencies=(), diagnostics=()))))
    draft = draft_for(input)
    field = ContinentalField(recipe=recipe, samples=tuple(zip(coords, values or (0.0,) * len(coords))))
    return input, type(draft).model_validate(draft.model_copy(update={"field": field}))
