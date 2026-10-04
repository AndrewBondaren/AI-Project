"""S3: pure wall classifier — provenance and owners, same wall set as pass3."""
import unittest
from itertools import permutations

from app.application.worldData.generators.structure.cellBuilder import (
    _interior, pass3_interior_walls,
)
from app.application.worldData.generators.structure.wallRegions import (
    classify_wall_regions,
)
from app.dataModel.locations.structure.wallRegion import WallProvenance
from tests.test_u_shape_orientation_baseline import room


def pass3_xy(rooms):
    return {(c.x, c.y) for c in
            pass3_interior_walls(rooms, [], 0, "world", "bld", "stone")}


def cell_map(regions):
    """coord → (provenance, room_keys); asserts single ownership."""
    out = {}
    for region in regions:
        for cell in region.cells:
            assert cell not in out, f"double ownership at {cell}"
            out[cell] = (region.provenance, region.room_keys)
    return out


def shaft(host_key=None, x=5, y=5, size=5, has_walls=True):
    s = room("shaft", x=x, y=y, width=size, depth=size)
    s.is_shaft = True
    s.shaft_has_walls = has_walls
    s.embedded_host_key = host_key
    return s


class WallRegionClassifierTests(unittest.TestCase):
    def assert_geometry(self, rooms, regions):
        union = set().union(*(r.cells for r in regions)) if regions else set()
        self.assertEqual(union, pass3_xy(rooms))
        seen = set()
        for region in regions:
            self.assertFalse(seen & region.cells)
            seen |= region.cells

    def test_adjacent_rooms_partition_interior_shell_exterior(self):
        a = room("a", x=0, y=0, width=7, depth=5)
        b = room("b", x=6, y=0, width=7, depth=5)
        regions = classify_wall_regions([a, b], 0, 3)
        self.assert_geometry([a, b], regions)
        cells = cell_map(regions)
        for y in (1, 2, 3):                      # partition body — both owners
            self.assertEqual(cells[(6, y)],
                             (WallProvenance.INTERIOR, ("a_0", "b_0")))
        for y in (0, 4):                         # partition ends touch air
            self.assertEqual(cells[(6, y)], (WallProvenance.EXTERIOR, ()))
        self.assertEqual(cells[(0, 0)], (WallProvenance.EXTERIOR, ()))
        interior = [c for c, (p, k) in cells.items()
                    if p == WallProvenance.INTERIOR]
        self.assertEqual(sorted(interior), [(6, 1), (6, 2), (6, 3)])

    def test_disjoint_rooms_are_all_exterior(self):
        a = room("a", x=0, y=0, width=5, depth=5)
        b = room("b", x=20, y=20, width=5, depth=5)
        regions = classify_wall_regions([a, b], 0, 0)
        self.assert_geometry([a, b], regions)
        cells = cell_map(regions)
        self.assertTrue(all(p == WallProvenance.EXTERIOR
                            for p, _ in cells.values()))

    def test_concave_notch_faces_are_exterior(self):
        t = room("t", x=0, y=0, width=7, depth=3)
        t.shape_type = "t_shape"
        t.shape_params = {"stem_width": 2, "stem_wall": "south"}
        regions = classify_wall_regions([t], 0, 2)
        self.assert_geometry([t], regions)
        cells = cell_map(regions)
        notch = {(x, y) for x in (0, 1, 4, 5, 6) for y in (-3, -2, -1)}
        facing_notch = {c for c in cells
                        if any((c[0]+dx, c[1]+dy) in notch
                               for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)))}
        self.assertTrue(facing_notch)
        for c in facing_notch:
            self.assertEqual(cells[c][0], WallProvenance.EXTERIOR, c)

    def test_enclosed_courtyard_walls_are_exterior(self):
        # Four rooms enclosing an empty 2-cell-wide courtyard column.
        west = room("west", x=0, y=4, width=5, depth=11)
        east = room("east", x=7, y=4, width=5, depth=11)
        north = room("north", x=4, y=11, width=4, depth=4)
        south = room("south", x=4, y=0, width=4, depth=4)
        rooms = [west, east, north, south]
        regions = classify_wall_regions(rooms, 0, 0)
        self.assert_geometry(rooms, regions)
        cells = cell_map(regions)
        courtyard = {(x, y) for x in (5, 6) for y in range(4, 11)}
        facing = {c for c in cells
                  if any((c[0]+dx, c[1]+dy) in courtyard
                         for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)))}
        self.assertTrue(facing)
        for c in facing:
            self.assertEqual(cells[c][0], WallProvenance.EXTERIOR, c)

    def test_closed_embedded_shaft_interior_host_is_single_candidate(self):
        host = room("host", x=0, y=0, width=15, depth=15)
        s = shaft(host.uid_key, x=5, y=5)
        regions = classify_wall_regions([host, s], 0, 2)
        self.assert_geometry([host, s], regions)
        cells = cell_map(regions)
        shaft_perim = s.get_footprint() - _interior(s.get_footprint())
        for c in shaft_perim:
            self.assertEqual(cells[c], (WallProvenance.INTERIOR, ("host_0",)), c)
        # Every region is either the shell or shaft enclosure.
        interior_cells = {c for c, (p, _) in cells.items()
                          if p == WallProvenance.INTERIOR}
        self.assertEqual(interior_cells, shaft_perim)

    def test_corner_embedded_shaft_shell_sides_stay_exterior(self):
        host = room("host", x=0, y=0, width=15, depth=15)
        s = shaft(host.uid_key, x=10, y=10)      # shares host's NE corner
        regions = classify_wall_regions([host, s], 0, 2)
        cells = cell_map(regions)
        shaft_perim = s.get_footprint() - _interior(s.get_footprint())
        on_shell = {c for c in shaft_perim
                    if any((c[0]+dx, c[1]+dy) not in host.get_footprint()
                           for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)))}
        inner = shaft_perim - on_shell
        self.assertTrue(on_shell and inner)
        for c in on_shell:
            self.assertEqual(cells[c][0], WallProvenance.EXTERIOR, c)
        for c in inner:
            self.assertEqual(cells[c], (WallProvenance.INTERIOR, ("host_0",)), c)

    def test_open_shaft_partitions_removed_but_shell_stays(self):
        host = room("host", x=0, y=0, width=15, depth=15)
        s = shaft(host.uid_key, x=5, y=5, has_walls=False)
        regions = classify_wall_regions([host, s], 0, 2)
        self.assert_geometry([host, s], regions)
        cells = cell_map(regions)
        shaft_perim = s.get_footprint() - _interior(s.get_footprint())
        self.assertFalse(set(cells) & shaft_perim)
        self.assertTrue(all(p == WallProvenance.EXTERIOR
                            for p, _ in cells.values()))

    def test_adjacent_shaft_shared_column_is_interior_host(self):
        host = room("host", x=0, y=0, width=10, depth=10)
        s = shaft(None, x=9, y=0, size=5)        # shares host's east column
        regions = classify_wall_regions([host, s], 0, 2)
        self.assert_geometry([host, s], regions)
        cells = cell_map(regions)
        shared = host.get_footprint() & s.get_footprint()
        interior_shared = {c for c in shared
                           if c in cells
                           and cells[c][0] == WallProvenance.INTERIOR}
        self.assertTrue(interior_shared)
        for c in interior_shared:
            self.assertEqual(cells[c], (WallProvenance.INTERIOR, ("host_0",)), c)

    def test_z_range_stamp_and_material_free_output(self):
        a = room("a", x=0, y=0, width=5, depth=5)
        regions = classify_wall_regions([a], 7, 10)
        self.assertTrue(all(r.z_min == 7 and r.z_max == 10 for r in regions))
        self.assertNotIn("material", WallRegionModelFields())
        for region in regions:
            self.assertIsInstance(region.cells, frozenset)

    def test_input_room_order_does_not_change_result(self):
        def scenario(order):
            a = room("a", x=0, y=0, width=7, depth=5)
            b = room("b", x=6, y=0, width=7, depth=5)
            c = room("c", x=6, y=4, width=7, depth=6)
            host = room("host", x=20, y=0, width=15, depth=15)
            s = shaft(host.uid_key, x=25, y=5)
            rooms = [a, b, c, host, s]
            return classify_wall_regions([rooms[i] for i in order], 0, 3)

        def signature(regions):
            return sorted((r.provenance, r.room_keys, tuple(sorted(r.cells)))
                          for r in regions)

        base = signature(scenario((0, 1, 2, 3, 4)))
        for order in permutations(range(5)):
            if order != (0, 1, 2, 3, 4):
                with self.subTest(order=order):
                    self.assertEqual(base, signature(scenario(order)))


def WallRegionModelFields():
    from app.dataModel.locations.structure.wallRegion import WallRegion
    return set(WallRegion.model_fields)
