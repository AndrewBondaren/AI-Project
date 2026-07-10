"""Fine terrain wire roundtrip preserves registry terrain keys."""

import unittest

from app.application.worldData.pack.mapCellToFineTerrainWire import cells_to_fine_terrain_chunk
from app.db.models.mapCell import MapCell


class TestMapCellL2Wire(unittest.TestCase):

    def test_terrain_roundtrip_keys(self):
        cells = [
            MapCell(world_uid="w", x=10, y=20, z=0, system_terrain="plains", system_material="earth"),
            MapCell(world_uid="w", x=10, y=20, z=1, system_terrain="plains", system_material="earth"),
            MapCell(world_uid="w", x=11, y=20, z=0, system_terrain="forest", system_material=None),
        ]
        chunk = cells_to_fine_terrain_chunk(0, 0, 32, 10, 20, cells)
        plains_run = chunk.columns[0].runs[0]
        self.assertEqual(plains_run.system_terrain, "plains")
        self.assertEqual(plains_run.system_material, "earth")
        forest_col = next(c for c in chunk.columns if c.lx == 1)
        self.assertEqual(forest_col.runs[0].system_terrain, "forest")


if __name__ == "__main__":
    unittest.main()
