"""LocationTerrainPackRenderer unit tests."""

import unittest

from app.application.worldData.render.locationTerrainPackRenderer import LocationTerrainPackRenderer
from app.application.worldData.render.renderPayloads import LEVEL_SURFACE
from app.dataModel.worldPack.fineTerrainChunkWire import (
    FineTerrainChunkWire,
    FineTerrainColumnWire,
    FineTerrainZRun,
)
from app.dataModel.worldPack.territoryVolume import TerritoryVolume


class TestLocationTerrainPackRenderer(unittest.TestCase):
    def _chunk(self) -> FineTerrainChunkWire:
        return FineTerrainChunkWire(
            cx=0,
            cy=0,
            chunk_columns=32,
            columns=[
                FineTerrainColumnWire(
                    lx=0,
                    ly=0,
                    runs=[
                        FineTerrainZRun(z0=0, z1=4, system_terrain="plains"),
                    ],
                ),
                FineTerrainColumnWire(
                    lx=1,
                    ly=0,
                    runs=[
                        FineTerrainZRun(z0=0, z1=2, system_terrain="plains"),
                        FineTerrainZRun(z0=3, z1=5, system_terrain="forest"),
                    ],
                ),
                FineTerrainColumnWire(
                    lx=0,
                    ly=1,
                    runs=[
                        FineTerrainZRun(z0=1, z1=3, system_terrain="liquid_body"),
                    ],
                ),
            ],
        )

    def test_surface_and_level(self):
        volume = TerritoryVolume(x0=100, y0=200, z0=0, x1=110, y1=210, z1=20)
        renderer = LocationTerrainPackRenderer(
            self._chunk(),
            volume=volume,
            location_uid="loc-a",
        )
        surface = renderer.render_surface_top()
        self.assertIn("pack location_terrain", surface)
        self.assertIn(".", surface)
        self.assertIn("f", surface)
        self.assertIn("~", surface)
        self.assertIn("territory meters x: 100..110", surface)

        at_z3 = renderer.render_level(3)
        self.assertIn("z=3", at_z3)
        self.assertIn(".", at_z3)  # plains at (0,0)
        self.assertIn("f", at_z3)  # forest at (1,0)
        self.assertIn("~", at_z3)  # liquid at (0,1)

        levels = renderer.render_all_levels()
        self.assertIn(LEVEL_SURFACE, levels)
        self.assertEqual(renderer.z_levels(), [0, 1, 2, 3, 4, 5])

    def test_legend(self):
        self.assertIn("plains", LocationTerrainPackRenderer.render_legend())


if __name__ == "__main__":
    unittest.main()
