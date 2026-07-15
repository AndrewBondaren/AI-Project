"""Unit tests — resolve_light_tile_cap, PackTilePlanner scopes, completeness."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.dataModel.worldPack.packBakeDefaults import (
    PackBakeDefaults,
    resolve_light_tile_cap,
)
from app.dataModel.worldPack.packCompleteness import PackCompletenessSnapshot
from app.dataModel.worldPack.packTilePlan import PackTileRef
from app.dataModel.worldPack.worldPackManifest import (
    LocationTerrainEntry,
    TileManifestEntry,
    WorldPackManifest,
)
from app.dataModel.worldPack.territoryVolume import TerritoryVolume


class TestResolveLightTileCap(unittest.TestCase):
    def test_none_uses_default(self):
        self.assertEqual(resolve_light_tile_cap(None), 16)

    def test_zero_uncapped(self):
        self.assertIsNone(resolve_light_tile_cap(0))

    def test_negative_uncapped(self):
        self.assertIsNone(resolve_light_tile_cap(-1))

    def test_positive(self):
        self.assertEqual(resolve_light_tile_cap(32), 32)

    def test_custom_defaults(self):
        defs = PackBakeDefaults(max_tiles_light=8)
        self.assertEqual(resolve_light_tile_cap(None, defaults=defs), 8)


class TestPackTilePlannerScopes(unittest.TestCase):
    def test_full_includes_all_location_tiles_without_cap(self):
        from app.application.worldData.pack.bake.packTilePlanner import PackTilePlanner
        from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
            SurfaceTerrainContext,
        )

        world = SimpleNamespace(
            world_uid="w1",
            map_cell_size_m=3000,
            hydrology=None,
        )
        locations = [
            SimpleNamespace(
                location_uid="a",
                map_x=0,
                map_y=0,
                map_z=0,
                system_location_type="geographic",
            ),
            SimpleNamespace(
                location_uid="b",
                map_x=3000 * 20,
                map_y=3000 * 20,
                map_z=0,
                system_location_type="geographic",
            ),
        ]
        # Minimal surface ctx
        ctx = MagicMock(spec=SurfaceTerrainContext)
        ctx.coarse_hydro = {}
        ctx.sparse_meter_hydro = {}

        with patch(
            "app.application.worldData.pack.bake.packTileCollect.is_hydrology_enabled",
            return_value=False,
        ), patch(
            "app.application.worldData.pack.bake.packTileCollect.static_map_anchors",
            side_effect=lambda locs: [loc for loc in locs if loc.map_x is not None],
        ), patch(
            "app.application.worldData.pack.bake.packTileCollect.cell_size_m",
            return_value=3000,
        ):
            plan = PackTilePlanner(bake_defaults=PackBakeDefaults(max_tiles_light=1)).plan(
                world, locations, ctx, scope="full",
            )
        self.assertEqual(plan.scope, "full")
        self.assertFalse(plan.capped)
        self.assertGreaterEqual(len(plan.tiles), 2)

        with patch(
            "app.application.worldData.pack.bake.packTilePlanner.bootstrap_macro_tiles",
            return_value=[(0, 0)],
        ):
            light = PackTilePlanner(bake_defaults=PackBakeDefaults(max_tiles_light=1)).plan(
                world, locations, ctx, scope="light", max_tiles=1,
            )
        self.assertEqual(len(light.tiles), 1)
        self.assertTrue(light.capped)


class TestPackCompletenessClassifier(unittest.TestCase):
    def test_absent_without_tiles(self):
        from app.application.worldData.pack.bake.packCompletenessClassifier import (
            PackCompletenessClassifier,
        )

        world = SimpleNamespace(world_uid="w1", map_cell_size_m=3000)
        snap = PackCompletenessClassifier().classify(
            world, [], manifest=None,
        )
        self.assertEqual(snap.completeness, "absent")

    def test_light_complete_when_baked_covers_light_not_full(self):
        from app.application.worldData.pack.bake.packCompletenessClassifier import (
            PackCompletenessClassifier,
        )
        from app.application.worldData.pack.bake.packTilePlanner import PackTilePlanner

        world = SimpleNamespace(world_uid="w1", map_cell_size_m=3000)
        planner = MagicMock(spec=PackTilePlanner)
        planner.plan.side_effect = [
            MagicMock(
                tiles=[PackTileRef(gx=0, gy=0)],
                scope="light",
                cap_applied=16,
            ),
            MagicMock(
                tiles=[PackTileRef(gx=0, gy=0), PackTileRef(gx=1, gy=1)],
                scope="full",
                cap_applied=None,
            ),
        ]
        manifest = WorldPackManifest(
            world_uid="w1",
            tiles=[
                TileManifestEntry(gx=0, gy=0, world_map_path="tiles/r.0.0.world_map.zst"),
            ],
        )
        with patch(
            "app.application.worldData.pack.bake.packCompletenessClassifier.prepare_surface_terrain_context",
            return_value=MagicMock(),
        ):
            snap = PackCompletenessClassifier(planner).classify(
                world, [], manifest=manifest, locations_index=None,
            )
        self.assertEqual(snap.completeness, "light_complete")
        self.assertEqual(snap.expected_l0_full, 2)
        self.assertEqual(len(snap.missing_l0_full), 1)
        self.assertEqual(snap.light_cap, 16)


if __name__ == "__main__":
    unittest.main()
