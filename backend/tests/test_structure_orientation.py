"""Variant B: rotated generation equals an independently rotated author frame."""
import json
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from tests.test_u_shape_orientation_baseline import room
from app.application.worldData.debugStructureRotations import RotationProbe, compare_rotation
from app.application.worldData.generators.structure.errors import GenerationError
from app.application.worldData.generators.structure.structureOrientation import StructureOrientation, entry_orientation
from app.dataModel.spatial.facing import Facing, CARDINAL_FACINGS
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.dataModel.locations.structure.enums.attachWall import AttachWall
from app.dataModel.locations.structure.room.entryPoint import EntryPoint
from app.db.models.mapCell import MapCell
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionEndpoint import TransitionEndpoint
from app.application.worldData.generators.structure.physicalTransition import physical_transition
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def simple_structure(wall="east"):
    return StructureTemplate(
        system_name="00000000-0000-4000-8000-000000000003", display_name="Orientation",
        levels=[{"z_offset": 0, "display_name": "Ground", "rooms": [{
            "room_id": "hall", "display_name": "Hall", "room_type": "common_hall",
            "shape_type": "rectangle", "size": {"width_range": [7,7], "depth_range": [5,5]},
            "required": True, "is_public": True, "is_forbidden": False,
            "entry_point": {"wall": wall, "passage_type": "main_entrance"},
        }]}],
    )


def test_world_building():
    world = World(world_uid="orientation-world", name="Orientation", created_at="2026-09-29")
    building = NamedLocation(
        location_uid="orientation-building", world_uid=world.world_uid, display_name="House",
        system_location_type="building", created_at="2026-09-29", map_x=23, map_y=-17, map_z=7,
    )
    return world, building


def rotate_point(point, pivot, turns):
    x, y = point[0] - pivot[0], point[1] - pivot[1]
    x, y = ((x,y), (-y,x), (-x,-y), (y,-x))[turns]
    return x + pivot[0], y + pivot[1]


class StructureOrientationTests(unittest.TestCase):
    def test_transform_inverse_and_four_turn_identity_for_all_runtime_fields(self):
        orientation = StructureOrientation((10,-5), 1)
        self.assertEqual(orientation.point(12,-2), (7,-3))
        self.assertEqual(orientation.inverse_point(7,-3), (12,-2))
        self.assertEqual(orientation.facing(Facing.EAST), Facing.NORTH)
        r = room(x=12, y=-2, width=3, depth=5)
        r.extra_cells = {(17,3)}
        r.entry_point = EntryPoint(wall=Facing.SOUTH, passage_type="main_entrance")
        r.back_entry_point = EntryPoint(wall=Facing.NORTH, passage_type="service_entrance")
        r.is_shaft = True
        r.facing = Facing.EAST.value
        r.embedded_entry = Facing.WEST
        r.attach_wall = AttachWall.NORTH
        cells = {(12,-2,7): MapCell("w",12,-2,7, system_facing="east", railing_sides=["N","E"])}
        passages = [physical_transition("w", "staircase", TransitionEndpoint(space="level", level_uid="l1", x=15, y=3, z=1), TransitionEndpoint(space="level", level_uid="l2", x=12, y=-2, z=0), "building")]
        original = deepcopy((cells, passages, [r]))
        orientation.apply(cells, passages, [r])
        self.assertEqual(r.width, 5)
        self.assertEqual(r.depth, 3)
        self.assertEqual(r.extra_cells, {orientation.point(17,3)})
        cell = next(iter(cells.values()))
        self.assertEqual(cell.railing_sides, ["W","N"])
        self.assertEqual(cell.system_facing, "north")
        for _ in range(3):
            orientation.apply(cells, passages, [r])
        self.assertEqual((cells, passages, [r]), original)

    def test_south_entrance_to_west_rotates_runtime_metadata_without_mutating_entries(self):
        entrance = room()
        entrance.entry_point = EntryPoint(wall=Facing.SOUTH, passage_type="main_entrance")
        entrance.back_entry_point = EntryPoint(wall=Facing.NORTH, passage_type="service_entrance")
        authored_entry, authored_back = entrance.entry_point, entrance.back_entry_point
        shaft = room("shaft", x=12, y=22)
        shaft.is_shaft = True
        shaft.facing = Facing.EAST.value
        shaft.embedded_entry = Facing.SOUTH
        passages = [physical_transition("w", "main_entrance", TransitionEndpoint(), TransitionEndpoint(space="level", level_uid="ground", x=13, y=20, z=0), "building")]
        orientation = entry_orientation([entrance, shaft], passages, "building", Facing.WEST)
        orientation.apply({}, passages, [entrance, shaft])
        self.assertEqual(entrance.entry_point.wall, Facing.WEST)
        self.assertEqual(entrance.back_entry_point.wall, Facing.EAST)
        self.assertEqual(shaft.facing, orientation.facing(Facing.EAST).value)
        self.assertIsInstance(shaft.facing, str)
        self.assertEqual(shaft.embedded_entry, orientation.facing(Facing.SOUTH))
        self.assertIsInstance(shaft.embedded_entry, Facing)
        self.assertIsNot(entrance.entry_point, authored_entry)
        self.assertIsNot(entrance.back_entry_point, authored_back)
        self.assertEqual(authored_entry.wall, Facing.SOUTH)
        self.assertEqual(authored_back.wall, Facing.NORTH)

    def test_attach_wall_cardinals_rotate_and_both_any_remain_invariant(self):
        for turns in range(4):
            orientation = StructureOrientation((10, 20), turns)
            for wall in AttachWall:
                with self.subTest(turns=turns, wall=wall):
                    placed = room()
                    placed.attach_wall = wall
                    orientation.apply({}, [], [placed])
                    expected = (AttachWall(orientation.facing(wall.value))
                                if wall in CARDINAL_FACINGS else wall)
                    self.assertEqual(placed.attach_wall, expected)
                    self.assertIsInstance(placed.attach_wall, AttachWall)

    def test_missing_shaft_directions_and_unplaced_rooms_are_preserved(self):
        for facing, embedded in ((None, None), (None, Facing.NORTH), ("east", None)):
            with self.subTest(facing=facing, embedded=embedded):
                shaft = room("shaft")
                shaft.is_shaft = True
                shaft.facing, shaft.embedded_entry = facing, embedded
                orientation = StructureOrientation((10, 20), 1)
                orientation.apply({}, [], [shaft])
                self.assertEqual(shaft.facing, None if facing is None else orientation.facing(facing).value)
                self.assertEqual(shaft.embedded_entry, None if embedded is None else orientation.facing(embedded))
                self.assertIsNone(shaft.entry_point)
                self.assertIsNone(shaft.back_entry_point)
        unplaced = room("unplaced", x=None, y=None)
        unplaced.entry_point = EntryPoint(wall=Facing.SOUTH, passage_type="main_entrance")
        unplaced.is_shaft = True
        unplaced.facing = "east"
        unplaced.embedded_entry = Facing.NORTH
        unplaced.attach_wall = AttachWall.SOUTH
        original = deepcopy(unplaced)
        StructureOrientation((10, 20), 1).apply({}, [], [unplaced])
        self.assertEqual(unplaced, original)

    def test_zero_turn_preserves_metadata_and_entry_identity(self):
        placed = room()
        placed.entry_point = EntryPoint(wall=Facing.SOUTH, passage_type="main_entrance")
        placed.back_entry_point = EntryPoint(wall=Facing.NORTH, passage_type="service_entrance")
        placed.is_shaft = True
        placed.facing = "east"
        placed.embedded_entry = Facing.WEST
        placed.attach_wall = AttachWall.SOUTH
        original = deepcopy(placed)
        entry, back = placed.entry_point, placed.back_entry_point
        StructureOrientation((10, 20), 0).apply({}, [], [placed])
        self.assertEqual(placed, original)
        self.assertIs(placed.entry_point, entry)
        self.assertIs(placed.back_entry_point, back)

    def test_invalid_facing_fails_before_instantiation(self):
        world, building = test_world_building()
        with patch.object(RotationProbe, "_instantiate_rooms") as instantiate:
            with self.assertRaises(GenerationError):
                RotationProbe().generate_from_template(world, building, simple_structure(), facing=Facing.NORTHEAST)
        instantiate.assert_not_called()

    def test_explicit_facing_requires_one_placed_main_entrance(self):
        world, building = test_world_building()
        for mode in ("missing", "multiple"):
            structure = simple_structure()
            definition = structure.levels[0]["rooms"][0]
            if mode == "missing":
                definition.pop("entry_point")
            else:
                definition["back_entry_point"] = {"wall": "west", "passage_type": "main_entrance"}
            RotationProbe().generate_from_template(world, building, structure)
            with self.assertRaises(GenerationError) as ctx:
                RotationProbe().generate_from_template(world, building, structure, facing=Facing.SOUTH)
            self.assertIn(str(structure.system_name), str(ctx.exception))
            self.assertIn("room_id candidates", str(ctx.exception))

    def test_full_generation_four_sides_matches_author_frame(self):
        root = Path(__file__).resolve().parents[2] / "structures_templates/base"
        structures = [simple_structure("east"), simple_structure("south")]
        from app.application.worldData.libraryPacks.uidMap import base_member_uid
        for uid in (base_member_uid("tavern_1"), base_member_uid("manor_1")):
            structures.append(StructureTemplate.model_validate(json.loads((root / (uid + ".json")).read_text(encoding="utf-8"))))
        world, building = test_world_building()
        for structure in structures:
            original = structure.model_dump()
            base_probe = RotationProbe()
            baseline = base_probe.generate_from_template(world, building, structure)
            for facing in sorted(CARDINAL_FACINGS):
                with self.subTest(structure=structure.display_name, facing=facing):
                    orientation = entry_orientation(base_probe.runtime_rooms, baseline.transitions, structure.system_name, facing)
                    probe = RotationProbe()
                    actual = probe.generate_from_template(world, building, structure, facing=facing)
                    expected_xyz = {(*rotate_point((c.x,c.y), orientation.pivot, orientation.quarter_turns), c.z) for c in baseline.cells}
                    self.assertEqual(expected_xyz, {(c.x,c.y,c.z) for c in actual.cells})
                    self.assertTrue(compare_rotation(baseline, base_probe, actual, probe, orientation, 7)["matches"])
                    for old, new in zip(base_probe.runtime_rooms, probe.runtime_rooms):
                        if not old.placed:
                            continue
                        points = [rotate_point((x,y), orientation.pivot, orientation.quarter_turns) for x in (old.origin_x, old.origin_x+old.width-1) for y in (old.origin_y, old.origin_y+old.depth-1)]
                        self.assertEqual((new.origin_x,new.origin_y), (min(p[0] for p in points), min(p[1] for p in points)))
                        for field in ("entry_point", "back_entry_point"):
                            old_entry, new_entry = getattr(old, field), getattr(new, field)
                            if old_entry is not None:
                                self.assertEqual(new_entry.wall, orientation.facing(old_entry.wall))
                        if old.is_shaft:
                            if old.facing is not None:
                                self.assertEqual(new.facing, orientation.facing(old.facing).value)
                            if old.embedded_entry is not None:
                                self.assertEqual(new.embedded_entry, orientation.facing(old.embedded_entry))
                    entrance = next(p for p in actual.transitions if p.system_transition_type == "main_entrance")
                    z = next(l.z for l in actual.levels if l.level_uid == entrance.destination.level_uid)
                    door = next(c for c in actual.cells if (c.x,c.y,c.z) == (entrance.destination.x,entrance.destination.y,z))
                    self.assertEqual(door.system_facing, facing)
            self.assertEqual(structure.model_dump(), original)

    def test_equivalence_detects_corrupted_facing(self):
        world, building = test_world_building()
        structure = simple_structure()
        bp, ap = RotationProbe(), RotationProbe()
        base = bp.generate_from_template(world, building, structure)
        actual = ap.generate_from_template(world, building, structure, facing=Facing.NORTH)
        orientation = entry_orientation(bp.runtime_rooms, base.transitions, structure.system_name, Facing.NORTH)
        actual.cells[0].system_facing = "west"
        self.assertFalse(compare_rotation(base, bp, actual, ap, orientation, 7)["matches"])
