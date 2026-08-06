"""Unit: Wave B5 polish — T-59 / T-61 / T-62 / T-63 / T-65."""

from __future__ import annotations

import json
import unittest
from dataclasses import dataclass, fields

from app.application.worldData.generators.terrain.relief.canalAttachments import (
    EMPTY_DRAW,
    project_canal_draw,
)
from app.application.worldData.generators.terrain.relief.gradePass import (
    RibbonGradeDecision,
)
from app.application.worldData.generators.terrain.relief.reliefEvents import (
    WHY_EMPTY_SAMPLE,
)
from app.application.worldData.generators.terrain.relief.ribbonSegmentize import (
    RibbonSegment,
)
from app.application.worldData.generators.terrain.relief.roadShoulderGrade import (
    RoadShoulderGradeResult,
)
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.roadShoulderApply import (
    apply_road_shoulder_grades,
)
from app.application.worldData.pack.bake.lightGrid.contributors.ribbonSampleUtil import (
    CARDINAL_ORTHO_DELTAS,
)
from app.application.worldData.pack.bake.lightGrid.contributors.roadShoulderSample import (
    sample_shoulder_cells,
)
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.application.worldData.pack.bake.lightGrid.roadShoulderIntent import to_intent
from app.dataModel.spatial.facing import CARDINAL_WALL_OUTWARD_DELTA, Facing
from app.dataModel.terrain.relief.canal import EarthenCanal
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexWire
from app.db.mapper import _deserialize, _serialize, json_list_col
from app.db.models.world import World


class OrthoFacingT62Test(unittest.TestCase):
    def test_ortho_from_facing_deltas(self) -> None:
        expected = tuple(
            CARDINAL_WALL_OUTWARD_DELTA[f]
            for f in (Facing.EAST, Facing.WEST, Facing.NORTH, Facing.SOUTH)
        )
        self.assertEqual(CARDINAL_ORTHO_DELTAS, expected)


class ProjectCanalDrawT63Test(unittest.TestCase):
    def test_omit_is_empty_draw(self) -> None:
        self.assertIs(project_canal_draw(None), EMPTY_DRAW)

    def test_extras_only(self) -> None:
        drawn = project_canal_draw(None, extra_structure_refs=("fence",))
        self.assertFalse(drawn.earthen_canal)
        self.assertEqual(drawn.structure_refs, ("fence",))

    def test_earthen_build(self) -> None:
        drawn = project_canal_draw(EarthenCanal())
        self.assertTrue(drawn.earthen_canal)


class IntentNoSynthesizeT61Test(unittest.TestCase):
    def test_non_skipped_does_not_synthesize_earthen(self) -> None:
        seg = RibbonSegment(
            owner_uid="e1",
            terrain_key="plains",
            system_terrain="plains",
            dz=1,
            site_id="s",
            cell_coords=((0, 0),),
        )
        decision = RibbonGradeDecision(
            template_uid="t1",
            policy=None,
            kind=ReliefSideKind.SHEER,
            requested_length=1,
            h=1,
            geom=None,
            earthen_canal=True,
            structure_refs=(),
            reason="ok",
            skipped=False,
            structure_canal=None,
        )
        result = RoadShoulderGradeResult(
            segment=seg, decision=decision, template_uid="t1",
        )
        intent = to_intent(result, ((0, 0),), canal=None)
        self.assertIsNone(intent.canal)
        self.assertIsNone(intent.earthen_canal)


class EmptySampleLogT65Test(unittest.TestCase):
    def test_sample_silent_apply_logs(self) -> None:
        scale = LightGridScale.from_tile(tile_m=320, side=32)
        compose = LightGridCompose(scale=scale)
        cell = compose.ensure(0, 0, 1, 1)
        cell.system_terrain = "road"
        cell.surface_z = 5
        # sample itself must not log
        with self.assertRaises(AssertionError):
            with self.assertLogs("app.relief", level="DEBUG"):
                sample_shoulder_cells(compose, {(1, 1)}, tile_set={(0, 0)})
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
            apply_road_shoulder_grades(
                compose, ctx, edge_uid="e1", road_cells={(1, 1)},
            )
        self.assertIn(WHY_EMPTY_SAMPLE, "\n".join(cm.output))


class JsonListColT59Test(unittest.TestCase):
    def test_empty_list_roundtrip_stays_list(self) -> None:
        @dataclass
        class Row:
            structure_refs: list = json_list_col()

        f = fields(Row)[0]
        dumped = _serialize(f, [])
        self.assertEqual(dumped, "[]")
        loaded = _deserialize(f, dumped)
        self.assertEqual(loaded, [])
        self.assertIsInstance(loaded, list)

    def test_null_and_object_hydrate_to_list(self) -> None:
        @dataclass
        class Row:
            structure_refs: list = json_list_col()

        f = fields(Row)[0]
        self.assertEqual(_deserialize(f, None), [])
        self.assertEqual(_deserialize(f, json.dumps({})), [])


if __name__ == "__main__":
    unittest.main()
