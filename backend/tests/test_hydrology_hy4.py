"""Unit tests for declare river carve — D HY-4."""

import unittest

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.terrain.hydrology.classifyRiverSegments import (
    segments_from_declared,
)
from app.application.worldData.generators.terrain.hydrology.riverBedCarver import (
    carve_river_segment,
)
from app.application.worldData.generators.terrain.hydrology.types import (
    DeclaredRiverEdge,
    RiverSegment,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole


def _flat(z: int = 10) -> SurfaceHeightmap:
    surface_z = {(gx, gy): z for gx in range(0, 12) for gy in range(0, 12)}
    return SurfaceHeightmap(
        world_uid="test",
        bbox=GridBBox(0, 11, 0, 11),
        surface_z=surface_z,
    )


class TestDeclareRiverSegments(unittest.TestCase):

    def test_segments_from_declared_keep_connection_type(self):
        edges = [
            DeclaredRiverEdge(
                edge_uid="ce-1",
                segment=((2, 2), (5, 2)),
                connection_type="mountain_river",
            ),
            DeclaredRiverEdge(
                edge_uid="ce-2",
                segment=((5, 2), (5, 5)),
                connection_type="river",
            ),
        ]
        segs = segments_from_declared(edges)
        self.assertEqual(len(segs), 2)
        self.assertEqual(segs[0].connection_type, "mountain_river")
        self.assertTrue(segs[0].declared)
        self.assertGreater(len(segs[0].polyline_cells), 1)


class TestRiverBedCarve(unittest.TestCase):

    def test_carve_lowers_z_and_sets_river_bed(self):
        hm = _flat()
        segment = RiverSegment(
            polyline_cells=[(3, 3), (4, 3), (5, 3)],
            connection_type="river",
            edge_uid="ce-test",
            declared=True,
        )
        carved = carve_river_segment(hm, segment, depth_step=1)
        self.assertEqual(len(carved), 3)
        self.assertEqual(hm.surface_z[(4, 3)], 9)
        self.assertEqual(carved[(4, 3)].role, HydrologyCellRole.RIVER_BED)
        self.assertEqual(carved[(4, 3)].connection_edge_uid, "ce-test")


if __name__ == "__main__":
    unittest.main()
