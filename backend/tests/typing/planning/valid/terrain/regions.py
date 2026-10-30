"""Positive terrain regions contracts; checked statically by Pyright."""

from typing import assert_type

from app.application.worldData.generators.terrain.regions.coverageMeasure import RegionCoverageMeasure
from app.application.worldData.generators.terrain.regions.regionExtent import (
    prepare_terrain_regions,
    require_terrain_region,
)
from app.application.worldData.masks.regionRasterContext import RasterWorld
from app.dataModel.spatial.grid.coordinateTypes import FineX
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage
from app.dataModel.terrain.regions.regionPlanningInput import TerrainRegionPlanningInput
from app.dataModel.terrain.regions.terrainRegionExtent import TerrainRegionExtent
from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionPlan


def valid_region_extent(world: RasterWorld, inputs: TerrainRegionPlanningInput, coverage: RegionCoverage) -> None:
    plan = prepare_terrain_regions(world, inputs=inputs)
    assert_type(plan, TerrainRegionPlan)
    assert_type(plan.snapshot.region_for("body"), TerrainRegionExtent | None)
    assert_type(require_terrain_region(plan.snapshot, world_uid=world.world_uid, snapshot_uid="snapshot", region_uid="body"), TerrainRegionExtent)
    assert_type(RegionCoverageMeasure.union((coverage,), region_uid="result"), RegionCoverage)
    assert_type(coverage.spans[0].x0, FineX)
