"""Unit tests — resolve_light_tile_cap, PackTilePlanner scopes, completeness."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.dataModel.worldPack.packBakeDefaults import (
    PackBakeDefaults,
    resolve_light_tile_cap,
)
from app.dataModel.worldPack.packTilePlan import PackTileRef
from app.dataModel.worldPack.worldPackManifest import (
    TileManifestEntry,
    WorldPackManifest,
)


class TestResolveLightTileCap(unittest.TestCase):
    def test_none_uses_default_uncapped(self):
        self.assertIsNone(resolve_light_tile_cap(None))

    def test_zero_uncapped(self):
        self.assertIsNone(resolve_light_tile_cap(0))

    def test_negative_uncapped(self):
        self.assertIsNone(resolve_light_tile_cap(-1))

    def test_positive(self):
        self.assertEqual(resolve_light_tile_cap(32), 32)

    def test_custom_defaults_positive(self):
        defs = PackBakeDefaults(max_tiles_light=8)
        self.assertEqual(resolve_light_tile_cap(None, defaults=defs), 8)


class TestPackTilePlannerScopes(unittest.TestCase):
    def test_light_is_all_location_tiles_full_is_world_bounds(self):
        from app.application.worldData.pack.bake.packTilePlanner import PackTilePlanner

        world = SimpleNamespace(
            world_uid="w1",
            map_cell_size_m=3000,
            hydrology=None,
            world_bounds=None,
            grid_bbox_padding=2,
            map_settings=None,
        )
        locations = [
            SimpleNamespace(
                location_uid="a",
                map_x=0,
                map_y=0,
                map_z=0,
                system_location_type="geographic",
                is_mobile=False,
            ),
            SimpleNamespace(
                location_uid="b",
                map_x=3000 * 4,
                map_y=3000 * 4,
                map_z=0,
                system_location_type="geographic",
                is_mobile=False,
            ),
        ]

        with patch(
            "app.application.worldData.pack.bake.packTileCollect.is_hydrology_enabled",
            return_value=False,
        ), patch(
            "app.application.worldData.pack.bake.packTileCollect.static_map_anchors",
            side_effect=lambda locs: list(locs),
        ), patch(
            "app.application.worldData.pack.bake.packTileCollect.cell_size_m",
            return_value=3000,
        ), patch(
            "app.application.worldData.generators.terrain.passes.bbox.static_map_anchors",
            side_effect=lambda locs: list(locs),
        ), patch(
            "app.application.worldData.generators.terrain.passes.bbox.cell_size_m",
            return_value=3000,
        ), patch(
            "app.application.worldData.generators.terrain.passes.bbox.grid_bbox_padding",
            return_value=2,
        ):
            planner = PackTilePlanner()
            light = planner.plan(world, locations, None, scope="light")
            full = planner.plan(world, locations, scope="full")

        self.assertEqual(light.scope, "light")
        self.assertFalse(light.capped)
        self.assertIsNone(light.cap_applied)
        self.assertEqual(len(light.tiles), 2)

        self.assertEqual(full.scope, "full")
        self.assertFalse(full.capped)
        # anchors at (0,0) and (4,4) ± padding 2 → indices -2..6 = 9×9
        self.assertEqual(len(full.tiles), 9 * 9)
        light_set = {t.as_tuple() for t in light.tiles}
        full_set = {t.as_tuple() for t in full.tiles}
        self.assertTrue(light_set <= full_set)

    def test_light_debug_cap_via_resolve(self):
        from app.application.worldData.pack.bake.packTilePlanner import PackTilePlanner

        world = SimpleNamespace(world_uid="w1", map_cell_size_m=3000, hydrology=None)
        locations: list = []

        with patch(
            "app.application.worldData.pack.bake.packTilePlanner.light_l0_tiles",
            return_value=[(0, 0), (1, 1), (2, 2)],
        ):
            light = PackTilePlanner(
                bake_defaults=PackBakeDefaults(max_tiles_light=0),
            ).plan(world, locations, scope="light", max_tiles=1)
        self.assertEqual(len(light.tiles), 1)
        self.assertTrue(light.capped)
        self.assertEqual(light.cap_applied, 1)

    def test_defaults_max_tiles_light_applies_when_max_tiles_none(self):
        from app.application.worldData.pack.bake.packTilePlanner import PackTilePlanner

        world = SimpleNamespace(world_uid="w1", map_cell_size_m=3000)
        with patch(
            "app.application.worldData.pack.bake.packTilePlanner.light_l0_tiles",
            return_value=[(0, 0), (1, 1), (2, 2)],
        ):
            light = PackTilePlanner(
                bake_defaults=PackBakeDefaults(max_tiles_light=2),
            ).plan(world, [], scope="light", max_tiles=None)
        self.assertEqual(len(light.tiles), 2)
        self.assertTrue(light.capped)
        self.assertEqual(light.cap_applied, 2)


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
                cap_applied=None,
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
        self.assertIsNone(snap.light_cap)
        # plan called with surface_ctx=None
        self.assertIsNone(planner.plan.call_args_list[0].args[2])


if __name__ == "__main__":
    unittest.main()
