"""A1: directed placement, protected entrances and runtime perimeter fallback."""
import unittest
from copy import deepcopy

from app.application.worldData.generators.structure.errors import GenerationError
from app.application.worldData.generators.structure.layoutEngine import layout_level, _place_next_to_any
from app.application.worldData.generators.structure.layoutEntry import entries_exterior
from app.dataModel.spatial.facing import Facing
from app.dataModel.locations.structure.room.entryPoint import EntryPoint
from app.dataModel.locations.structure.building.roomConnection import RoomConnection
from tests.test_u_shape_orientation_baseline import room
from tests.test_structure_orientation import simple_structure, test_world_building
from app.application.worldData.debugStructureRotations import RotationProbe


def entry(wall, width=1):
    return EntryPoint(wall=wall, passage_type="main_entrance", width=width)


def unplaced(name, **kwargs):
    result = room(name, **kwargs)
    result.origin_x = result.origin_y = None
    return result


def layout(rooms, pairs=()):
    connections = [RoomConnection(from_room=a, to_room=b, passage_type="doorway") for a, b in pairs]
    layout_level(rooms, connections, 10, 20, staircases=[],
                 building_uid="entry-layout", world_uid="w")


class EntryLayoutTests(unittest.TestCase):
    def test_neighbor_with_either_entry_keeps_its_wall_exterior(self):
        for field in ("entry_point", "back_entry_point"):
            for wall in (Facing.NORTH, Facing.SOUTH, Facing.EAST, Facing.WEST):
                with self.subTest(field=field, wall=wall):
                    anchor, neighbor = room("anchor"), unplaced("neighbor")
                    setattr(neighbor, field, entry(wall))
                    layout([anchor, neighbor], [("anchor", "neighbor")])
                    if wall is Facing.WEST:
                        self.assertLess(neighbor.origin_x, anchor.origin_x)
                    self.assertTrue(entries_exterior(neighbor, anchor.get_footprint() | neighbor.get_footprint()))

    def test_later_rooms_do_not_cover_start_or_back_entrance(self):
        start, neighbor, isolated = unplaced("start"), unplaced("neighbor"), unplaced("isolated")
        start.entry_point = entry(Facing.EAST)
        start.back_entry_point = entry(Facing.WEST)
        original = (start.entry_point, start.back_entry_point)
        layout([start, neighbor, isolated], [("start", "neighbor")])
        union = set().union(*(r.get_footprint() for r in (start, neighbor, isolated)))
        self.assertTrue(entries_exterior(start, union))
        self.assertEqual((start.entry_point, start.back_entry_point), original)

    def test_occupied_edge_tries_shifted_slot_before_fallback(self):
        anchor = room("anchor")
        blocker = room("blocker", x=10, y=26, width=3, depth=7)
        candidate = unplaced("candidate", width=3)
        candidate.entry_point = entry(Facing.NORTH)
        with self.assertNoLogs("app.application.worldData.generators.structure.layoutEntry", "WARNING"):
            self.assertTrue(_place_next_to_any(candidate, [anchor, blocker]))
        self.assertEqual(candidate.origin_y, 26)
        self.assertGreater(candidate.origin_x, 10)
        self.assertEqual(candidate.entry_point.wall, Facing.NORTH)

    def test_fallback_warns_and_changes_only_runtime_entry(self):
        anchor, candidate = room("anchor"), unplaced("candidate", width=9, depth=3)
        authored = entry(Facing.EAST, width=3)
        candidate.entry_point = authored
        with self.assertLogs("app.application.worldData.generators.structure.layoutEntry", "WARNING") as logs:
            self.assertTrue(_place_next_to_any(candidate, [anchor]))
        self.assertEqual(len(logs.records), 1)
        self.assertIn("entry_point.wall=east unreachable", logs.output[0])
        self.assertIn("candidate", logs.output[0])
        self.assertEqual(authored.wall, Facing.EAST)
        self.assertNotEqual(candidate.entry_point.wall, Facing.EAST)
        self.assertTrue(entries_exterior(candidate, anchor.get_footprint() | candidate.get_footprint()))

    def test_no_perimeter_raises_even_for_optional_entry_room(self):
        candidate = unplaced("no-perimeter", width=3, depth=3)
        candidate.entry_point = entry(Facing.NORTH, width=2)
        candidate.required = False
        with self.assertRaisesRegex(GenerationError, "no exterior perimeter"):
            layout([candidate])

    def test_optional_connected_entry_cannot_be_silently_skipped(self):
        anchor, candidate = room("anchor"), unplaced("no-perimeter", width=3, depth=3)
        candidate.back_entry_point = entry(Facing.NORTH, width=2)
        candidate.required = False
        with self.assertRaisesRegex(GenerationError, "no exterior perimeter"):
            layout([anchor, candidate], [("anchor", "no-perimeter")])

    def test_nonrectangular_entry_uses_actual_footprint(self):
        candidate = unplaced("round", width=9, depth=9)
        candidate.shape_type = "circle"
        candidate.entry_point = entry(Facing.WEST)
        anchor = room("anchor", width=9, depth=9)
        layout([anchor, candidate], [("anchor", "round")])
        self.assertTrue(entries_exterior(candidate, anchor.get_footprint() | candidate.get_footprint()))
        self.assertEqual(candidate.entry_point.wall, Facing.WEST)

    def test_generation_keeps_both_entrances_and_template_is_immutable(self):
        template = simple_structure("east")
        template.levels[0]["rooms"][0]["back_entry_point"] = {
            "wall": "west", "passage_type": "service_entrance",
        }
        neighbor = deepcopy(template.levels[0]["rooms"][0])
        neighbor.update(room_id="kitchen", display_name="Kitchen")
        neighbor.pop("entry_point")
        neighbor.pop("back_entry_point")
        template.levels[0]["rooms"].append(neighbor)
        template.connections.append(dict(from_room="hall", to_room="kitchen", passage_type="doorway"))
        before = deepcopy(template.model_dump())
        world, building = test_world_building()
        runs = [RotationProbe().generate_from_template(world, building, template) for _ in range(2)]
        self.assertEqual(runs[0].cells, runs[1].cells)
        self.assertEqual(runs[0].passages, runs[1].passages)
        self.assertEqual(template.model_dump(), before)
        self.assertEqual({p.system_passage_type for p in runs[0].passages},
                         {"main_entrance", "service_entrance", "doorway"})
