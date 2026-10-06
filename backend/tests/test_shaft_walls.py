"""B4: open shaft partitions, preserved building shell and unchanged stair path."""
import unittest
from copy import deepcopy
from unittest.mock import patch

from app.application.worldData.debugStructureRotations import RotationProbe
from app.application.worldData.generators.structure.cellBuilder import (
    _interior, pass2_floors, pass3_interior_walls,
)
from app.application.worldData.generators.structure.passages.archway import _build_archway
from app.dataModel.locations.structure.enums.buildingElement import StructureElement
from tests import test_embedded_shaft
from tests.test_structure_orientation import test_world_building
from tests.test_u_shape_orientation_baseline import room

BUILDER = "app.application.worldData.generators.structure.passages.builder"


class ShaftWallTests(unittest.TestCase):
    def cell_rooms(self, embedded=True, center=False, has_walls=False):
        host = room("host", x=0, y=0, width=15, depth=15)
        xy = (5, 5) if center else ((10, 10) if embedded else (14, 0))
        shaft = room("shaft", x=xy[0], y=xy[1], width=5, depth=5)
        shaft.is_shaft = True
        shaft.shaft_has_walls = has_walls
        if embedded:
            shaft.embedded_host_key = host.uid_key
        return host, shaft

    def walls(self, rooms):
        return {(c.x, c.y) for c in pass3_interior_walls(rooms, [], 0, "world", "building", "stone")}

    def test_center_open_removes_only_shaft_walls_closed_keeps_them(self):
        for has_walls in (False, True):
            with self.subTest(has_walls=has_walls):
                host, shaft = self.cell_rooms(center=True, has_walls=has_walls)
                host_wall = host.get_footprint() - _interior(host.get_footprint())
                shaft_wall = shaft.get_footprint() - _interior(shaft.get_footprint())
                self.assertEqual(self.walls([host, shaft]), host_wall | (shaft_wall if has_walls else set()))
                floors = {(c.x, c.y) for c in pass2_floors([host, shaft], 0, "world", {host.uid_key: "host"})}
                hole = shaft.get_footprint() if has_walls else _interior(shaft.get_footprint())
                self.assertEqual(floors, host.get_footprint() - hole)

    def test_corner_open_preserves_shared_exterior_host_walls(self):
        host, shaft = self.cell_rooms()
        host_wall = host.get_footprint() - _interior(host.get_footprint())
        self.assertEqual(self.walls([host, shaft]), host_wall)

    def test_adjacent_open_removes_partition_but_keeps_building_shell(self):
        host, shaft = self.cell_rooms(embedded=False)
        union = host.get_footprint() | shaft.get_footprint()
        partition = (host.get_footprint() & shaft.get_footprint()) & _interior(union)
        closed = (host.get_footprint() - _interior(host.get_footprint())) | (
            shaft.get_footprint() - _interior(shaft.get_footprint()))
        self.assertEqual(self.walls([host, shaft]), closed - partition)
        self.assertFalse(self.walls([host, shaft]) & partition)
        self.assertTrue((union - _interior(union)) <= self.walls([host, shaft]))

    def test_open_and_closed_generate_same_xy_and_stair_path(self):
        world, building = test_world_building()
        for at in ("center", "north_east"):
            runs = []
            for has_walls in (False, True):
                template = test_embedded_shaft.EmbeddedShaftTests().template(at)
                template.staircases[0]["has_walls"] = has_walls
                before = deepcopy(template.model_dump())
                probe = RotationProbe()
                with patch(BUILDER + "._build_archway", wraps=_build_archway) as arches:
                    result = probe.generate_from_template(world, building, template)
                self.assertEqual(arches.call_count, 2 if has_walls else 0)
                self.assertEqual(template.model_dump(), before)
                shafts = [r for r in probe.runtime_rooms if r.is_shaft]
                self.assertTrue(all(r.shaft_has_walls == has_walls for r in shafts))
                geometry = [(r.room_id, r.origin_x, r.origin_y, r.width, r.depth) for r in probe.runtime_rooms]
                path = {(c.x, c.y, c.z, c.system_facing) for c in result.cells
                        if c.system_building_element == StructureElement.STAIRCASE}
                runs.append((geometry, path))
                landing = next(p for p in result.transitions if p.system_transition_type == "staircase")
                z = next(l.z for l in result.levels if l.level_uid == landing.destination.level_uid)
                cell = next(c for c in result.cells if (c.x, c.y, c.z) == (landing.destination.x, landing.destination.y, z))
                self.assertEqual(cell.system_building_element, StructureElement.FLOOR)
            self.assertEqual(runs[0], runs[1], at)

    def test_adjacent_open_generation_has_floor_exit_and_no_automatic_arches(self):
        world, building = test_world_building()
        template = test_embedded_shaft.EmbeddedShaftTests().template("north_east")
        template.staircases[0].update(in_a_room=False, has_walls=False)
        template.staircases[0].pop("embed_at")
        template.staircases[0].pop("embed_in")
        probe = RotationProbe()
        with patch(BUILDER + "._build_archway", wraps=_build_archway) as arches:
            first = probe.generate_from_template(world, building, template)
        self.assertEqual(arches.call_count, 0)
        second = RotationProbe().generate_from_template(world, building, template)
        self.assertEqual((first.cells, first.transitions), (second.cells, second.transitions))
        landing = next(p for p in first.transitions if p.system_transition_type == "staircase")
        z = next(l.z for l in first.levels if l.level_uid == landing.destination.level_uid)
        cell = next(c for c in first.cells if (c.x, c.y, c.z) == (landing.destination.x, landing.destination.y, z))
        self.assertEqual(cell.system_building_element, StructureElement.FLOOR)

    def test_all_march_types_obey_wall_flag_at_cell_generation(self):
        for stair_type in ("straight", "u_shape", "spiral"):
            for has_walls in (False, True):
                host, shaft = self.cell_rooms(center=True, has_walls=has_walls)
                shaft.staircase_type = stair_type
                shaft_wall = shaft.get_footprint() - _interior(shaft.get_footprint())
                self.assertEqual(bool(self.walls([host, shaft]) & shaft_wall), has_walls)
