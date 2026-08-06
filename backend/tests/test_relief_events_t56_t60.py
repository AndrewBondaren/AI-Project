"""Unit: RELIEF-T-56 event tokens + RELIEF-T-60 silent-path logs (Wave B2/B3)."""

from __future__ import annotations

import unittest

from app.application.worldData.generators.terrain.relief import canalAttachments
from app.application.worldData.generators.terrain.relief.reliefEvents import (
    EVENT_RESOLVE_FALLBACK,
    EVENT_RIBBON_BARRIER,
    EVENT_RIBBON_SKIP,
    REASON_SCHEDULE_HOLE_SAFE_SLOPE,
    WHY_EMPTY_SAMPLE,
    WHY_HEIGHT_LT_1,
    WHY_NO_EDGE_ROAD_ANCHOR,
    WHY_NO_REF_CELLS,
    WHY_NO_TEMPLATES,
    WHY_NOT_STAMPED,
    WHY_SCHEDULE_HOLE,
)
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.roadShoulderApply import (
    apply_road_shoulder_grades,
)
from app.application.worldData.pack.bake.lightGrid.contributors.roadShoulderSample import (
    sample_shoulder_cells,
)
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexWire
from app.db.models.world import World


class ReliefEventsTokensTest(unittest.TestCase):
    def test_shared_resolve_fallback_reexported_from_canal(self) -> None:
        self.assertEqual(canalAttachments.EVENT_RESOLVE_FALLBACK, EVENT_RESOLVE_FALLBACK)
        self.assertEqual(EVENT_RESOLVE_FALLBACK, "resolve_fallback")
        self.assertEqual(EVENT_RIBBON_BARRIER, "ribbon_barrier")
        self.assertEqual(WHY_SCHEDULE_HOLE, "schedule_hole")
        self.assertEqual(REASON_SCHEDULE_HOLE_SAFE_SLOPE, "schedule_hole_safe_slope")
        self.assertEqual(WHY_HEIGHT_LT_1, "height_lt_1")
        self.assertEqual(WHY_NO_EDGE_ROAD_ANCHOR, "no_edge_road_anchor")
        self.assertEqual(WHY_NOT_STAMPED, "not_stamped")
        self.assertEqual(EVENT_RIBBON_SKIP, "ribbon_skip")
        self.assertEqual(WHY_NO_REF_CELLS, "no_ref_cells")


class ReliefSilentPathLogsTest(unittest.TestCase):
    def test_apply_early_exit_no_road_logged(self) -> None:
        scale = LightGridScale.from_tile(tile_m=320, side=32)
        compose = LightGridCompose(scale=scale)
        world = World(
            world_uid="w1", name="W", created_at="2026-01-01T00:00:00Z",
        )
        ctx = LightGridBakeContext(
            world=world,
            locations=[],
            locations_index=LocationsIndexWire(locations=[]),
            tiles=[(0, 0)],
            scale=scale,
            relief_templates_by_uid={"t": None},  # type: ignore[dict-item]
        )
        with self.assertLogs("app.relief", level="DEBUG") as cm:
            out = apply_road_shoulder_grades(
                compose, ctx, owner_uid="e1", road_cells=set(),
            )
        self.assertEqual(out, [])
        blob = "\n".join(cm.output)
        self.assertIn(EVENT_RIBBON_SKIP, blob)
        self.assertIn(WHY_NO_REF_CELLS, blob)

    def test_apply_early_exit_no_templates_logged(self) -> None:
        scale = LightGridScale.from_tile(tile_m=320, side=32)
        compose = LightGridCompose(scale=scale)
        world = World(
            world_uid="w1", name="W", created_at="2026-01-01T00:00:00Z",
        )
        ctx = LightGridBakeContext(
            world=world,
            locations=[],
            locations_index=LocationsIndexWire(locations=[]),
            tiles=[(0, 0)],
            scale=scale,
            relief_templates_by_uid={},
        )
        with self.assertLogs("app.relief", level="DEBUG") as cm:
            out = apply_road_shoulder_grades(
                compose, ctx, owner_uid="e1", road_cells={(1, 1)},
            )
        self.assertEqual(out, [])
        blob = "\n".join(cm.output)
        self.assertIn(WHY_NO_TEMPLATES, blob)

    def test_sample_empty_silent_t65(self) -> None:
        scale = LightGridScale.from_tile(tile_m=320, side=32)
        compose = LightGridCompose(scale=scale)
        cell = compose.ensure(0, 0, 1, 1)
        cell.system_terrain = "road"
        cell.surface_z = 5
        # T-65: sample does not log; apply owns WHY_EMPTY_SAMPLE
        out = sample_shoulder_cells(compose, {(1, 1)}, tile_set={(0, 0)})
        self.assertEqual(out, [])
        self.assertEqual(WHY_EMPTY_SAMPLE, "empty_sample")


if __name__ == "__main__":
    unittest.main()
