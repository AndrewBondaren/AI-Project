"""WorldGridRenderer unit tests."""

import unittest

from app.application.worldData.render.worldGridRenderer import WorldGridRenderer
from app.db.models.mapCell import MapCell


class TestWorldGridRenderer(unittest.TestCase):

    def test_render_bbox_symbols(self):
        cells = [
            MapCell(
                world_uid="w",
                x=3000, y=3000, z=5,
                system_terrain="plains",
                hydrology='{"role": "river_bed"}',
            ),
            MapCell(
                world_uid="w",
                x=6000, y=3000, z=3,
                system_terrain="liquid_body",
                hydrology='{"role": "coastal_sea"}',
            ),
        ]
        grid = WorldGridRenderer(cells, cell_size_m=3000).render_bbox(1, 1, 2, 1)
        self.assertIn("r", grid)
        self.assertIn("~", grid)

    def test_render_legend(self):
        legend = WorldGridRenderer.render_legend()
        self.assertIn("river_bed", legend)
        self.assertIn("plains", legend)

    def test_render_auto_bbox(self):
        cells = [
            MapCell(world_uid="w", x=0, y=0, z=1, system_terrain="plains"),
            MapCell(world_uid="w", x=6000, y=3000, z=1, system_terrain="forest"),
        ]
        out = WorldGridRenderer(cells, cell_size_m=3000).render()
        self.assertIn("grid gx: 0..2", out)
        self.assertIn("cell_size_m=3000", out)


if __name__ == "__main__":
    unittest.main()
