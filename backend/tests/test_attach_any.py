"""§6.6 A1–A5: corridor ANY selects one side without changing shared RNG."""
import unittest
from copy import deepcopy
from unittest.mock import patch

from app.application.worldData.generators.structure.layoutEngine import _layout_mode_b
from app.application.worldData.generators.structure.structureGeneratorService import StructureGeneratorService
from app.dataModel.spatial.facing import Facing
from app.dataModel.locations.structure.building.staircaseSpec import StaircaseSpec
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.dataModel.locations.structure.enums.attachWall import AttachWall
from app.ids import UidKind, entity_rng
from tests.structureWire import room_wire, level_wire
from tests.test_u_shape_orientation_baseline import room
from tests.test_structure_orientation import test_world_building

LAYOUT = "app.application.worldData.generators.structure.layoutEngine"


def scenario(width=10, depth=14, room_type="corridor", mode=AttachWall.ANY, z=0):
    host = room("corridor", width=width, depth=depth, z=z)
    host.room_type = room_type
    attached = [room(f"guest_{index}", x=None, y=None, width=5, depth=5, z=z) for index in range(2)]
    for guest in attached:
        guest.attach_to = host.room_id
        guest.attach_wall = mode
    return host, attached


def staircase(facing, ident="stairs", z=0, stops=None):
    spec = StaircaseSpec(staircase_id=ident, stops=stops or ["corridor", "upper"], facing=facing)
    shaft = room("shaft_" + ident, x=None, y=None, z=z)
    shaft.is_shaft = True
    shaft.staircase_id = ident
    return spec, shaft


def place(host, attached, pairs=(), building_uid="attach-test"):
    specs = [spec for spec, _ in pairs]
    shafts = [shaft for _, shaft in pairs if shaft is not None]
    _layout_mode_b([host, *attached, *shafts], [host], staircases=specs,
                   building_uid=building_uid, world_uid="w")


class AttachAnyTests(unittest.TestCase):
    def assert_side(self, host, attached, side):
        for guest in attached:
            self.assertTrue(guest.placed)
            if side == Facing.SOUTH:
                self.assertEqual(guest.origin_y + guest.depth - 1, host.origin_y)
            elif side == Facing.NORTH:
                self.assertEqual(guest.origin_y, host.origin_y + host.depth - 1)
            elif side == Facing.WEST:
                self.assertEqual(guest.origin_x + guest.width - 1, host.origin_x)
            else:
                self.assertEqual(guest.origin_x, host.origin_x + host.width - 1)

    def test_staircase_occupies_one_side_on_each_host_axis(self):
        for width, depth, facing, expected in (
            (10, 14, Facing.NORTH, Facing.SOUTH), (10, 14, Facing.SOUTH, Facing.NORTH),
            (14, 10, Facing.EAST, Facing.WEST), (14, 10, Facing.WEST, Facing.EAST),
            (10, 10, Facing.NORTH, Facing.SOUTH),
        ):
            with self.subTest(width=width, depth=depth, facing=facing):
                host, guests = scenario(width, depth)
                with patch(LAYOUT + ".entity_rng", side_effect=AssertionError("one free side needs no RNG")):
                    place(host, guests, [staircase(facing)])
                self.assert_side(host, guests, expected)

    def test_ambiguous_cases_use_keyed_choice_on_host_axis(self):
        for width, depth, sides in ((10, 14, (Facing.NORTH, Facing.SOUTH)),
                                    (14, 10, (Facing.EAST, Facing.WEST))):
            for uid in ("building-a", "building-b"):
                for z in (0, 2):
                    perpendicular = Facing.EAST if depth >= width else Facing.NORTH
                    cases = [[], [staircase(None, z=z)], [staircase(perpendicular, z=z)],
                             [staircase(sides[0], "one", z), staircase(sides[1], "two", z)]]
                    for pairs in cases:
                        with self.subTest(width=width, uid=uid, z=z, pairs=len(pairs)):
                            host, guests = scenario(width, depth, z=z)
                            expected = entity_rng(
                                "w", UidKind.STRUCTURE, building=uid,
                                room=host.room_id, z_offset=z,
                                tag=AttachWall.ANY,
                            ).choice(sides)
                            place(host, guests, pairs, uid)
                            self.assert_side(host, guests, expected)

    def test_only_matching_stop_and_shaft_on_this_level_count(self):
        north, _ = staircase(Facing.NORTH)
        ignored = [(north, None), staircase(Facing.NORTH, z=1),
                   staircase(Facing.NORTH, stops=["elsewhere", "upper"])]
        for other in ignored:
            with self.subTest(other=other):
                host, guests = scenario()
                place(host, guests, [staircase(Facing.SOUTH, "south"), other])
                self.assert_side(host, guests, Facing.NORTH)

    def test_union_and_order_independence_includes_all_stops(self):
        for reverse in (False, True):
            host, guests = scenario()
            pairs = [staircase(Facing.NORTH, "one"),
                     staircase(Facing.NORTH, "two", stops=["lower", "corridor"])]
            place(host, guests, list(reversed(pairs)) if reverse else pairs)
            self.assert_side(host, guests, Facing.SOUTH)

    def test_intercardinal_projection_without_relaxing_wire_validation(self):
        # Internal typed values may be supplied by future callers; wire remains cardinal-only.
        for width, depth, direction, expected in (
            (10, 14, Facing.NORTHEAST, Facing.SOUTH),
            (10, 14, Facing.SOUTHWEST, Facing.NORTH),
            (14, 10, Facing.NORTHEAST, Facing.WEST),
            (14, 10, Facing.NORTHWEST, Facing.EAST),
        ):
            host, guests = scenario(width, depth)
            spec, shaft = staircase(Facing.NORTH)
            spec = spec.model_copy(update={"facing": direction})
            place(host, guests, [(spec, shaft)])
            self.assert_side(host, guests, expected)

    def test_both_non_corridor_any_and_explicit_sides_keep_old_behavior(self):
        for width, depth in ((10, 14), (14, 10)):
            for kind, mode in (("corridor", AttachWall.BOTH), ("common_hall", AttachWall.ANY)):
                host, guests = scenario(width, depth, kind, mode)
                place(host, guests, [staircase(Facing.NORTH)])
                sides = (Facing.NORTH, Facing.SOUTH) if width >= depth else (Facing.EAST, Facing.WEST)
                self.assert_side(host, guests[:1], sides[0])
                self.assert_side(host, guests[1:], sides[1])
        for side in (Facing.NORTH, Facing.SOUTH, Facing.EAST, Facing.WEST):
            host, guests = scenario(mode=AttachWall(side.value))
            place(host, guests, [staircase(side)])
            self.assert_side(host, guests, side)

    def test_service_wiring_and_generate_twice_with_and_without_staircase(self):
        world, building = test_world_building()
        for has_staircase in (False, True):
            corridor = room_wire(room_id="corridor", room_type="corridor",
                size={"width_range": [10, 10], "depth_range": [14, 14]},
                entry_point={"wall": "west", "passage_type": "main_entrance"})
            guest = room_wire(room_id="guest", attach_to="corridor", attach_wall="any", count=2,
                              size={"width_range": [5, 5], "depth_range": [5, 5]})
            levels = [level_wire(rooms=[corridor, guest])]
            staircases = []
            if has_staircase:
                levels.append(level_wire(z_offset=1, rooms=[room_wire(room_id="upper",
                    size={"width_range": [10, 10], "depth_range": [14, 14]})]))
                staircases.append(dict(staircase_id="stairs", stops=["corridor", "upper"],
                                       facing="north", size={"size_type": "sq_small"}))
            template = StructureTemplate(system_name="00000000-0000-4000-8000-000000000066",
                                         display_name="ANY", levels=levels, staircases=staircases)
            original = deepcopy(template.model_dump())
            expected = Facing.SOUTH if has_staircase else entity_rng(
                world.world_uid, UidKind.STRUCTURE,
                building=building.location_uid, room="corridor", z_offset=0,
                tag=AttachWall.ANY,
            ).choice((Facing.NORTH, Facing.SOUTH))
            def capture(*args, **kwargs):
                _layout_mode_b(*args, **kwargs)
                if args[0][0].z_offset == 0:
                    host = next(r for r in args[0] if r.room_id == "corridor")
                    guests = [r for r in args[0] if r.room_id == "guest"]
                    self.assertEqual(len(guests), 2)
                    self.assert_side(host, guests, expected)
            with self.subTest(staircase=has_staircase), patch(LAYOUT + "._layout_mode_b", side_effect=capture):
                first = StructureGeneratorService().generate_from_template(world, building, template)
                second = StructureGeneratorService().generate_from_template(world, building, template)
                self.assertTrue(first.cells)
                self.assertEqual(first.cells, second.cells)
                self.assertEqual(first.transitions, second.transitions)
                self.assertEqual(first.levels, second.levels)
                self.assertEqual(template.model_dump(), original)
