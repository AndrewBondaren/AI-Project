"""Surface-only skeleton (N_base=0) with cliff gap compensation."""

from __future__ import annotations

import unittest

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.terrain.passes.columnFillPass import run_column_fill
from app.application.worldData.generators.terrain.passes.gapAnalysisPass import run_gap_analysis
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.db.models.world import World


def _world(*, depth: int = 0) -> World:
    return World(
        world_uid="w-surface-gap",
        name="Gap Test",
        created_at="2026-01-01T00:00:00Z",
        map_subsurface_depth=depth,
        map_cell_size_m=3000,
        terrain_registry=[
            {
                "system_terrain": "plains",
                "terrain_category": "solid",
                "travel_modifier": 1.5,
                "danger_level": "none",
                "has_state": False,
            },
            {
                "system_terrain": "mountain",
                "terrain_category": "solid",
                "travel_modifier": 3.0,
                "danger_level": "medium",
                "has_state": False,
            },
        ],
    )


class TerrainSurfaceGapTest(unittest.TestCase):

    def test_flat_column_surface_only(self) -> None:
        world = _world(depth=0)
        heightmap = SurfaceHeightmap(
            world_uid=world.world_uid,
            bbox=GridBBox(x_min=0, x_max=1, y_min=0, y_max=0),
            surface_z={(0, 0): 10, (1, 0): 10},
        )
        n_eff = run_gap_analysis(world, heightmap)
        self.assertEqual(n_eff[(0, 0)], 0)
        cells = run_column_fill(world, heightmap, n_eff)
        self.assertEqual(len(cells), 2)
        self.assertEqual({c.z for c in cells}, {10})

    def test_cliff_extends_down_to_neighbor_surface(self) -> None:
        world = _world(depth=0)
        heightmap = SurfaceHeightmap(
            world_uid=world.world_uid,
            bbox=GridBBox(x_min=0, x_max=1, y_min=0, y_max=0),
            surface_z={(0, 0): 12, (1, 0): 5},
        )
        n_eff = run_gap_analysis(world, heightmap)
        self.assertEqual(n_eff[(0, 0)], 7)
        cells_hi = [c for c in run_column_fill(world, heightmap, n_eff) if c.x == 0]
        zs = sorted(c.z for c in cells_hi)
        self.assertEqual(zs, [5, 6, 7, 8, 9, 10, 11, 12])
        cells_lo = [c for c in run_column_fill(world, heightmap, n_eff) if c.x == 1]
        self.assertEqual(len(cells_lo), 1)
        self.assertEqual(cells_lo[0].z, 5)


if __name__ == "__main__":
    unittest.main()
