"""L0 full_bake AABB wrap seam — WorldBounds.antagonist_tile."""

from __future__ import annotations

import unittest

from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.application.worldData.pack.bake.lightGrid.worldSeam import apply_world_seam
from app.dataModel.spatial.facing import CARDINAL_WALL_OUTWARD_DELTA, Facing
from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole
from app.dataModel.worldPack.worldBounds import WorldBounds


class TestLightGridRim(unittest.TestCase):
    def test_rim_follows_outward_delta(self) -> None:
        scale = LightGridScale.from_tile(4, 3)
        last = scale.side - 1
        dx, dy = CARDINAL_WALL_OUTWARD_DELTA[Facing.WEST]
        self.assertLess(dx, 0)
        west = scale.rim_tx_ty(Facing.WEST)
        self.assertEqual(west[0][0], 0)
        self.assertEqual(len(west), scale.side)
        east = scale.rim_tx_ty(Facing.EAST)
        self.assertEqual(east[0][0], last)
        south = scale.rim_tx_ty(Facing.SOUTH)
        self.assertEqual(south[0][1], 0)
        north = scale.rim_tx_ty(Facing.NORTH)
        self.assertEqual(north[0][1], last)


class TestWorldSeam(unittest.TestCase):
    def test_owner_west_rim_copied_to_antagonist_east(self) -> None:
        scale = LightGridScale.from_tile(4, 2)
        compose = LightGridCompose(scale)
        bounds = WorldBounds(x_min=0, x_max=2, y_min=0, y_max=0)
        last = scale.side - 1
        for ty in range(scale.side):
            owner = compose.ensure(0, 0, 0, ty)
            owner.surface_z = 9
            owner.system_terrain = "mountain"
            ant = compose.ensure(2, 0, last, ty)
            ant.surface_z = 1
            ant.system_terrain = "plains"
            ant.hydrology_role = WorldMapHydrologyRole.RIVER
        n = apply_world_seam(compose, bounds, [(0, 0), (2, 0)], world_seed="w")
        self.assertEqual(n, 1)
        for ty in range(scale.side):
            ant = compose.get(2, 0, last, ty)
            assert ant is not None
            self.assertEqual(ant.surface_z, 9)
            self.assertEqual(ant.system_terrain, "mountain")
            self.assertEqual(ant.hydrology_role, WorldMapHydrologyRole.RIVER)

    def test_skips_antagonist_not_in_tiles(self) -> None:
        scale = LightGridScale.from_tile(4, 2)
        compose = LightGridCompose(scale)
        bounds = WorldBounds(x_min=0, x_max=2, y_min=0, y_max=0)
        last = scale.side - 1
        compose.ensure(0, 0, 0, 0).surface_z = 9
        compose.ensure(2, 0, last, 0).surface_z = 1
        n = apply_world_seam(compose, bounds, [(0, 0)])
        self.assertEqual(n, 0)
        self.assertEqual(compose.get(2, 0, last, 0).surface_z, 1)

    def test_skips_one_tile_wide_world(self) -> None:
        scale = LightGridScale.from_tile(4, 2)
        compose = LightGridCompose(scale)
        bounds = WorldBounds(x_min=3, x_max=3, y_min=0, y_max=0)
        last = scale.side - 1
        compose.ensure(3, 0, 0, 0).surface_z = 9
        compose.ensure(3, 0, last, 0).surface_z = 1
        n = apply_world_seam(compose, bounds, [(3, 0)])
        self.assertEqual(n, 0)
        self.assertEqual(compose.get(3, 0, last, 0).surface_z, 1)


if __name__ == "__main__":
    unittest.main()
