"""Fine terrain wire roundtrip preserves registry terrain keys."""

import unittest

from app.application.worldData.pack.read.mapCellToFineTerrainWire import cells_to_fine_terrain_chunk
from app.dataModel.worldPack.fineTerrainChunkWire import FineTerrainColumnWire, FineTerrainZRun
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

    def test_column_facing_surface_only(self):
        """PAR-T-1: mid-z facing must not win over empty surface."""
        cells = [
            MapCell(
                world_uid="w", x=0, y=0, z=0,
                system_terrain="mountain", system_facing="north",
            ),
            MapCell(
                world_uid="w", x=0, y=0, z=1,
                system_terrain="mountain", system_facing=None,
            ),
        ]
        chunk = cells_to_fine_terrain_chunk(0, 0, 32, 0, 0, cells)
        self.assertIsNone(chunk.columns[0].system_facing)

    def test_column_facing_roundtrip(self):
        cells = [
            MapCell(
                world_uid="w", x=0, y=0, z=0,
                system_terrain="mountain",
            ),
            MapCell(
                world_uid="w", x=0, y=0, z=1,
                system_terrain="mountain", system_facing="north",
            ),
        ]
        chunk = cells_to_fine_terrain_chunk(0, 0, 32, 0, 0, cells)
        self.assertEqual(chunk.columns[0].system_facing, "north")
        dumped = FineTerrainColumnWire.model_validate(
            chunk.columns[0].model_dump(mode="json"),
        )
        self.assertEqual(dumped.system_facing, "north")

    def test_fine_terrain_facing_is_enum(self):
        from app.dataModel.spatial.facing import Facing

        col = FineTerrainColumnWire(
            lx=0,
            ly=0,
            runs=[FineTerrainZRun(z0=0, z1=0, system_terrain="plains")],
            system_facing="north",
        )
        self.assertIs(col.system_facing, Facing.NORTH)
        with self.assertRaises(Exception):
            FineTerrainColumnWire(
                lx=0,
                ly=0,
                runs=[FineTerrainZRun(z0=0, z1=0, system_terrain="plains")],
                system_facing="not-a-facing",
            )

    def test_column_grade_uid_surface_only(self):
        """PAR-G9: mid-z uid must not win over empty surface."""
        cells = [
            MapCell(
                world_uid="w", x=0, y=0, z=0,
                system_terrain="plains", system_grade_uid="g-mid",
            ),
            MapCell(
                world_uid="w", x=0, y=0, z=1,
                system_terrain="plains", system_grade_uid=None,
            ),
        ]
        chunk = cells_to_fine_terrain_chunk(0, 0, 32, 0, 0, cells)
        self.assertIsNone(chunk.columns[0].system_grade_uid)

        cells_surface = [
            MapCell(
                world_uid="w", x=0, y=0, z=0,
                system_terrain="plains",
            ),
            MapCell(
                world_uid="w", x=0, y=0, z=1,
                system_terrain="plains",
                system_grade_uid="g1",
                system_facing="east",
            ),
        ]
        chunk2 = cells_to_fine_terrain_chunk(0, 0, 32, 0, 0, cells_surface)
        self.assertEqual(chunk2.columns[0].system_grade_uid, "g1")
        dumped = FineTerrainColumnWire.model_validate(
            chunk2.columns[0].model_dump(mode="json"),
        )
        self.assertEqual(dumped.system_grade_uid, "g1")
        # Legacy blob without field → None
        legacy = FineTerrainColumnWire.model_validate(
            {"lx": 0, "ly": 0, "runs": [{"z0": 0, "z1": 0, "system_terrain": "plains"}]},
        )
        self.assertIsNone(legacy.system_grade_uid)


if __name__ == "__main__":
    unittest.main()
