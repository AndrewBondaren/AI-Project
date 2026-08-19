"""LocationTerrainPackRenderer unit tests."""

import unittest

from app.application.worldData.render.gradeRayDump import GradeRayIndex
from app.application.worldData.render.locationTerrainPackRenderer import LocationTerrainPackRenderer
from app.application.worldData.render.renderPayloads import (
    LEVEL_SURFACE,
    LEVEL_SURFACE_GRADE,
    LEVEL_SURFACE_Z,
    grade_level_key,
)
from app.dataModel.spatial.facing import Facing
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.gradeRimRay import GradeRimRay
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
        self.assertIn("_", surface)
        self.assertIn("f", surface)
        self.assertIn("~", surface)
        self.assertIn("territory meters x: 100..110", surface)

        at_z3 = renderer.render_level(3)
        self.assertIn("z=3", at_z3)
        self.assertIn("_", at_z3)  # plains at (0,0)
        self.assertIn("f", at_z3)  # forest at (1,0)
        self.assertIn("~", at_z3)  # liquid at (0,1)

        levels = renderer.render_all_levels()
        self.assertIn(LEVEL_SURFACE, levels)
        self.assertIn(LEVEL_SURFACE_Z, levels)
        self.assertIn(" 5", levels[LEVEL_SURFACE_Z])  # forest column top z=5
        self.assertNotIn(LEVEL_SURFACE_GRADE, levels)  # PAR-G4: no uid → omit
        self.assertEqual(renderer.z_levels(), [0, 1, 2, 3, 4, 5])

    def test_grade_level_crop_and_omit(self):
        chunk = FineTerrainChunkWire(
            cx=0,
            cy=0,
            chunk_columns=32,
            columns=[
                FineTerrainColumnWire(
                    lx=0,
                    ly=0,
                    runs=[FineTerrainZRun(z0=0, z1=1, system_terrain="plains")],
                    system_grade_uid="g1",
                    system_facing="north",
                ),
                FineTerrainColumnWire(
                    lx=2,
                    ly=0,
                    runs=[FineTerrainZRun(z0=0, z1=1, system_terrain="plains")],
                    system_grade_uid="g1",
                    system_facing=None,
                ),
                FineTerrainColumnWire(
                    lx=5,
                    ly=5,
                    runs=[FineTerrainZRun(z0=0, z1=1, system_terrain="forest")],
                ),
            ],
        )
        volume = TerritoryVolume(x0=0, y0=0, z0=0, x1=10, y1=10, z1=5)
        renderer = LocationTerrainPackRenderer(
            chunk, volume=volume, location_uid="loc-g",
            ray_index=GradeRayIndex((
                GradeRimRay(
                    x=0, y=0, facing=Facing.NORTH, kind=ReliefSideKind.SLOPE,
                ),
                GradeRimRay(
                    x=2, y=0, facing=Facing.SOUTH, kind=ReliefSideKind.SHEER,
                ),
            )),
        )
        grade = renderer.render_grade()
        self.assertIn("↑", grade)
        self.assertIn("┃", grade)
        self.assertIn("f", grade)  # surface center, not occupancy overlay
        self.assertNotIn("grade:", grade)  # PAR-T-6: legend not in body
        mid = [ln for ln in grade.splitlines() if ln.startswith("   0 |")]
        self.assertEqual(len(mid), 1)
        self.assertIn("_", mid[0])
        self.assertNotIn("↑", mid[0])  # north ray is the row above gy label
        levels = renderer.render_all_levels(include_column_diagnostics=False)
        self.assertIn(LEVEL_SURFACE_GRADE, levels)
        # surface_z == 1 for both grade columns → grade_1 only
        self.assertIn(grade_level_key(1), levels)
        self.assertIn("↑", levels[grade_level_key(1)])
        self.assertIn("_", levels[grade_level_key(1)])  # material underlay at z
        at_z0 = renderer.render_grade_at_z(0)
        self.assertEqual(at_z0, "")

    def test_legend(self):
        self.assertIn("plains", LocationTerrainPackRenderer.render_legend())


if __name__ == "__main__":
    unittest.main()
