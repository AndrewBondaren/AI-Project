"""LocationGridRenderer unit tests."""

import unittest

from app.application.worldData.render.locationGridRenderer import LocationGridRenderer
from app.db.models.mapCell import MapCell


class TestLocationGridRenderer(unittest.TestCase):

    def test_render_level_outdoor(self):
        cells = [
            MapCell(
                world_uid="w",
                location_uid="loc-a",
                x=0, y=0, z=0,
                system_terrain="plains",
            ),
            MapCell(
                world_uid="w",
                location_uid="loc-a",
                x=1, y=0, z=0,
                system_terrain="forest",
            ),
            MapCell(
                world_uid="w",
                location_uid="loc-b",
                x=5, y=5, z=0,
                system_terrain="plains",
            ),
        ]
        out = LocationGridRenderer(cells, "loc-a").render_level(0)
        self.assertIn("location=loc-a", out)
        self.assertIn(".", out)
        self.assertIn("f", out)
        self.assertNotIn("loc-b", out)

    def test_render_all_levels(self):
        cells = [
            MapCell(
                world_uid="w",
                location_uid="loc-a",
                x=0, y=0, z=0,
                system_terrain="plains",
            ),
            MapCell(
                world_uid="w",
                location_uid="loc-a",
                x=0, y=0, z=1,
                system_terrain="plains",
            ),
        ]
        levels = LocationGridRenderer(cells, "loc-a").render_all_levels()
        self.assertEqual(set(levels.keys()), {0, 1})


if __name__ == "__main__":
    unittest.main()
