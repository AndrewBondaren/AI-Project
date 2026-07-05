"""Grid builder smoke tests."""

import unittest

from app.application.worldData.render.worldGridBuilder import WorldGridBuilder
from app.db.models.mapCell import MapCell


class TestWorldGridBuilder(unittest.TestCase):

    def test_build_bbox_symbols(self):
        cells = [
            MapCell(
                world_uid="w",
                x=1, y=1, z=5,
                system_terrain="plains",
                hydrology='{"role": "river_bed"}',
            ),
            MapCell(
                world_uid="w",
                x=2, y=1, z=3,
                system_terrain="liquid_body",
                hydrology='{"role": "coastal_sea"}',
            ),
        ]
        grid = WorldGridBuilder(cells).build_bbox(1, 1, 2, 1)
        self.assertIn("r", grid)
        self.assertIn("~", grid)


if __name__ == "__main__":
    unittest.main()
