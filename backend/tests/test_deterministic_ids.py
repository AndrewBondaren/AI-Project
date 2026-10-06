"""DET-1 — canonical formula, three roots, closed kinds, source gate.

SoT: docs/project_data_storage_tz.md § «Детерминированные uid и rng».
Plan: .cursor/plans/deterministic-ids-done.md.

Gate: uuid5/uuid4/Random(/random.seed/hashlib-seed и импорт legacy
``app.utils.deterministicIds`` вне ``application/worldData/ids`` запрещены;
постоянные исключения (content_hash, runtime ids вне worldData, dataModel
authored fallback) — в ``_EXEMPT``.
"""

import hashlib
import json
import re
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import NAMESPACE_DNS, UUID, uuid5

from app.application.worldData.generators.structure.staircase.uShape.uShapeHelper import _compute_fr_anchor, _compute_u_params
from app.application.worldData.generators.structure.structureGeneratorService import StructureGeneratorService
from app.application.worldData.ids import (
    LibraryKind,
    UidKind,
    entity_rng,
    entity_uid,
    library_uid,
    runtime_uid,
    seed_int,
    seed_rng,
    seed_root,
    seed_uid,
)
from app.dataModel.spatial.facing import Facing
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.dataModel.locations.structure.enums.buildingElement import StructureElement
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


class DetIdsContractTests(unittest.TestCase):
    def test_canonical_format_sorted_keys(self):
        uid = entity_uid(
            "w1", UidKind.TRANSITION,
            b=(12, 4, -1), a=(12, 4, 0), type="hatch",
        )
        self.assertEqual(
            uid,
            str(uuid5(
                NAMESPACE_DNS,
                "w1|transition|a=12,4,0|b=12,4,-1|type=hatch",
            )),
        )

    def test_key_order_does_not_change_uid(self):
        a = entity_uid("w", UidKind.AREA, min_x=1, min_y=2, facing=Facing.NORTH)
        b = entity_uid("w", UidKind.AREA, facing=Facing.NORTH, min_y=2, min_x=1)
        self.assertEqual(a, b)

    def test_normalization(self):
        uid = entity_uid("w", UidKind.LEVEL, z_offset=2, flag=True)
        self.assertEqual(
            uid,
            str(uuid5(NAMESPACE_DNS, "w|level|flag=1|z_offset=2")),
        )

    def test_none_and_unsupported_values_rejected(self):
        with self.assertRaises(ValueError):
            entity_uid("w", UidKind.LEVEL, z_offset=None)
        with self.assertRaises(ValueError):
            entity_uid("w", UidKind.LEVEL, z_offset={"x": 1})

    def test_unknown_kind_rejected(self):
        with self.assertRaises(ValueError):
            entity_uid("w", "no-such-kind")

    def test_seed_root_and_int(self):
        world = World(world_uid="w-123", name="W", created_at="2026-01-01")
        self.assertEqual(seed_root(world), "w-123")
        self.assertEqual(
            seed_int(world),
            int(hashlib.md5(b"w-123").hexdigest()[:8], 16),
        )
        with self.assertRaises(ValueError):
            seed_root(object())

    def test_rng_replay_and_stream_isolation(self):
        keys = {"building": "b", "staircase": "s", "tag": "fr_anchor"}
        first = entity_rng("w", UidKind.STAIR, **keys)
        expected = [first.random() for _ in range(8)]
        other = entity_rng("w", UidKind.STAIR, **{**keys, "building": "other"})
        for _ in range(100):
            other.random()
        replay = entity_rng("w", UidKind.STAIR, **keys)
        self.assertEqual(expected, [replay.random() for _ in range(8)])
        self.assertNotEqual(
            expected[0],
            entity_rng("w", UidKind.STAIR, **{**keys, "building": "x"}).random(),
        )

    def test_seed_rng_replay(self):
        a = seed_rng("seed", UidKind.RELIEF_PICK, site="tile:0,0", k=1)
        b = seed_rng("seed", UidKind.RELIEF_PICK, site="tile:0,0", k=1)
        self.assertEqual(a.random(), b.random())

    def test_seed_uid(self):
        self.assertEqual(
            seed_uid("seed", UidKind.GRADE_FACE, site="tile:0,0|face:V|1,2"),
            str(uuid5(
                NAMESPACE_DNS,
                "seed|grade_face|site=tile:0,0|face:V|1,2",
            )),
        )

    def test_library_uid(self):
        a = library_uid(LibraryKind.BUILDING_TEMPLATES, "house")
        self.assertEqual(a, library_uid(LibraryKind.BUILDING_TEMPLATES, "house"))
        self.assertNotEqual(
            a, library_uid(LibraryKind.RELIEF_TEMPLATES, "house"),
        )
        UUID(a)

    def test_runtime_uid(self):
        a, b = runtime_uid(), runtime_uid()
        self.assertNotEqual(a, b)
        UUID(a)


_BANNED = (
    ("uuid5", re.compile(r"\buuid5\(")),
    ("uuid4", re.compile(r"\buuid4\(")),
    ("Random(", re.compile(r"\bRandom\(")),
    ("random.seed", re.compile(r"\brandom\.seed\(")),
    ("hashlib", re.compile(r"\bhashlib\.(md5|sha1|sha256)\(")),
    ("legacy helper import", re.compile(r"app\.utils\.deterministicIds")),
)

# Permanent exceptions — not entity/rng identity sites.
_EXEMPT = (
    "application/worldData/deriveWorldUid.py",                 # world_uid derivation
    "application/worldData/pack/io/",                          # content_hash integrity
    "application/worldData/pack/import_/packImportService.py", # content_hash
    "application/chat/chatService.py",                         # runtime ids (D8)
    "application/worldData/playerService.py",                  # runtime ids (D8)
    "application/worldData/gameSessionService.py",             # runtime ids (D8)
    "core/logMiddleware.py",                                   # request id
    # dataModel cannot import application/worldData/ids (layer) — authored
    # fallback mint; system_name is UNIQUE in perk/race_templates (step 8)
    "dataModel/perks/perkTemplateOutline.py",
    "dataModel/races/raceTemplateOutline.py",
)

class SourceGateTests(unittest.TestCase):
    def test_no_det_id_formula_outside_ids(self):
        app_root = Path(__file__).resolve().parents[1] / "app"
        violations: dict[str, list[str]] = {}
        for path in sorted(app_root.rglob("*.py")):
            rel = path.relative_to(app_root).as_posix()
            if rel.startswith("application/worldData/ids/"):
                continue
            text = path.read_text(encoding="utf-8")
            hits = sorted(
                {name for name, rx in _BANNED if rx.search(text)}
            )
            if hits:
                violations[rel] = hits

        unexpected = {
            rel: hits for rel, hits in violations.items()
            if not rel.startswith(_EXEMPT)
        }
        self.assertEqual(
            unexpected, {},
            "det-id formula sites outside worldData/ids — route through the "
            f"helper or register a documented _EXEMPT: {unexpected}",
        )


class StaircaseReplayTests(unittest.TestCase):
    """Formula-agnostic: generation must replay anchors and cells."""

    def test_anchor_keeps_free_corner_fallback_and_previous_corner(self):
        args = (10, 20, 3, 3, Facing.NORTH)
        rng = entity_rng("b", UidKind.STAIR, tag="s")
        selected, _, _ = _compute_fr_anchor(*args, rng=rng)
        cells = {(*selected, 0): MapCell("w", *selected, 0, system_building_element=StructureElement.WALL)}
        fallback, _, _ = _compute_fr_anchor(
            *args, cells=cells, rng=entity_rng("b", UidKind.STAIR, tag="s"),
        )
        self.assertNotEqual(selected, fallback)
        previous, _, _ = _compute_fr_anchor(
            *args, prev_fr_anchor=selected, cells=cells,
            rng=entity_rng("b", UidKind.STAIR, tag="other"),
        )
        self.assertEqual(previous, selected)

    def test_generate_replays_u_shape_anchors_and_cells(self):
        path = Path(__file__).resolve().parents[2] / "structures_templates/base/7c3a4d5e-6f7a-4b8c-8d9e-1f2a3b4c5d6e.json"
        structure = StructureTemplate.model_validate(json.loads(path.read_text(encoding="utf-8")))
        original = structure.model_dump()
        world = World(world_uid="rng-world", name="RNG", created_at="2026-09-29")
        building = NamedLocation(
            location_uid="rng-building", world_uid=world.world_uid,
            display_name="Manor", system_location_type="building", created_at="2026-09-29",
            map_x=20, map_y=30, map_z=7,
        )
        module = "app.application.worldData.generators.structure.staircase.uShape.uShape"

        def generate():
            anchors = []

            def capture(*args, **kwargs):
                params = _compute_u_params(*args, **kwargs)
                anchors.append(params.fr_anchor)
                return params

            with patch(module + "._compute_u_params", side_effect=capture), patch("random.choice", side_effect=AssertionError("global RNG used")):
                layout = StructureGeneratorService().generate_from_template(world, building, structure)
            self.assertTrue(anchors)
            stairs = [c for c in layout.cells if c.system_building_element in (
                StructureElement.STAIRCASE, StructureElement.STAIR_ANCHOR, StructureElement.STAIR_FLOOR,
            )]
            self.assertTrue(stairs)
            return anchors, stairs, layout

        first = generate()
        second = generate()
        self.assertEqual(first[:2], second[:2])
        before, after = first[2], second[2]
        self.assertEqual(before.cells, after.cells)
        self.assertEqual(before.levels, after.levels)
        self.assertEqual(before.transitions, after.transitions)
        self.assertEqual(before.occupied_footprint, after.occupied_footprint)
        self.assertEqual(
            [replace(room, created_at="") for room in before.rooms],
            [replace(room, created_at="") for room in after.rooms],
        )
        self.assertEqual(structure.model_dump(), original)


if __name__ == "__main__":
    unittest.main()
