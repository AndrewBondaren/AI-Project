"""Unit: Wave B5 polish — T-59 / T-62 / T-63 (L0 shoulder apply removed R36u-T-8)."""

from __future__ import annotations

import json
import unittest
from dataclasses import dataclass, fields

from app.application.worldData.generators.terrain.relief.canalAttachments import (
    EMPTY_DRAW,
    project_canal_draw,
)
from app.application.worldData.generators.terrain.relief.facing import (
    CARDINAL_ORTHO_DELTAS,
)
from app.dataModel.spatial.facing import CARDINAL_WALL_OUTWARD_DELTA, Facing
from app.dataModel.terrain.relief.canal import EarthenCanal
from app.db.mapper import _deserialize, _serialize, json_list_col


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
