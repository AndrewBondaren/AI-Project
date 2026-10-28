"""Exact coarse intersection weights through the terrain geometry owner."""

from unittest import TestCase

from app.application.worldData.generators.terrain.regions.coverageMeasure import RegionCoverageMeasure
from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan, RegionCoverage


class CoarseCoverageMeasureTests(TestCase):
    def test_span_intersections_match_discrete_membership_for_negative_sparse_and_split_rows(self):
        coverage = RegionCoverage(region_uid="region", spans=(
            CoverageSpan(y=-3, x0=-5, x1=-1), CoverageSpan(y=-3, x0=1, x1=4),
            CoverageSpan(y=-2, x0=-3, x1=3), CoverageSpan(y=0, x0=0, x1=5)))
        fine_cells = frozenset((x, s.y) for s in coverage.spans for x in range(s.x0, s.x1))
        cells = tuple(SurfaceGridCoord(x, y) for y in range(-3, 3) for x in range(-3, 3))
        for side in (1, 2, 3, 5):
            grid = SurfaceGridSettings(fine_span=side, light_side=7)
            expected = tuple(sum((x, y) in fine_cells
                for y in range(c.gy * side, (c.gy + 1) * side)
                for x in range(c.gx * side, (c.gx + 1) * side)) for c in cells)
            self.assertEqual(RegionCoverageMeasure.coarse_cell_areas(coverage, cells, grid), expected)

    def test_empty_coverage_and_arbitrary_cell_order_are_preserved(self):
        cells = (SurfaceGridCoord(2, 2), SurfaceGridCoord(0, 0), SurfaceGridCoord(2, 2))
        grid = SurfaceGridSettings(fine_span=2, light_side=3)
        self.assertEqual(RegionCoverageMeasure.coarse_cell_areas(RegionCoverage(region_uid="empty", spans=()), cells, grid), (0, 0, 0))
        coverage = RegionCoverage(region_uid="region", spans=(CoverageSpan(y=0, x0=0, x1=1),))
        self.assertEqual(RegionCoverageMeasure.coarse_cell_areas(coverage, cells, grid), (0, 1, 0))

    def test_huge_sparse_coordinates_do_not_require_a_fine_world_array(self):
        coordinate = 10 ** 12
        coverage = RegionCoverage(region_uid="region", spans=(CoverageSpan(y=coordinate, x0=coordinate, x1=coordinate + 1),))
        self.assertEqual(RegionCoverageMeasure.coarse_cell_areas(coverage,
            (SurfaceGridCoord(coordinate // 4, coordinate // 4),), SurfaceGridSettings(fine_span=4, light_side=3)), (1,))
