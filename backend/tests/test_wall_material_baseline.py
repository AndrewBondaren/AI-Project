"""S1: characterize current wall material behaviour (structure-wall-materials).

Baseline contract (observed, pre-fix):
  * every wall cell gets the single ``wall_material`` argument (building
    material); resolved ``room.wall_material`` is stored on _RoomInstance and
    propagated to NamedLocation, but the wall writer never consumes it;
  * floors already carry per-room ``floor_material``; door/archway frame cells
    already use ``conn.frame_material or fr.wall_material``;
  * allowed post-fix diff: ``system_material`` on wall cells only — geometry,
    elements, openings, passages, RNG and diagnostics are regression gates.
"""
import unittest
from dataclasses import asdict

from app.application.worldData.debugStructureRotations import RotationProbe
from app.application.worldData.generators.structure.cellBuilder import (
    _interior, build_level_cells, pass3_interior_walls,
)
from app.application.worldData.generators.structure.structureOrientation import (
    entry_orientation,
)
from app.dataModel.locations.structure.building.structureTemplate import (
    StructureTemplate,
)
from app.dataModel.locations.structure.enums.buildingElement import (
    StructureElement,
)
from app.dataModel.materials import DEFAULT_WALL_MATERIAL
from app.dataModel.spatial.facing import CARDINAL_FACINGS
from app.db.models.namedLocation import NamedLocation
from tests import test_embedded_shaft
from tests.structureWire import level_wire, room_wire
from tests.test_structure_orientation import rotate_point, test_world_building
from tests.test_u_shape_orientation_baseline import room

_NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))
_BASELINE_TEMPLATE_ID = "00000000-0000-4000-8000-000000000021"

# Wire rows for world.material_registry — canonical fixture rows carry no
# "construction" tags, so without these every resolve falls back to defaults.
_WORLD_MATERIALS = [
    {"system_material": "oak", "display_name": "Oak",
     "material_category": "solid", "tags": ["construction"],
     "use_type": ["wall", "floor"], "economic_tier": "basic",
     "structural_strength": 0.3},
    {"system_material": "granite", "display_name": "Granite",
     "material_category": "solid", "tags": ["construction"],
     "use_type": ["wall", "floor"], "economic_tier": "standard",
     "structural_strength": 0.9},
]


def _walls(cells):
    return {(c.x, c.y, c.z): c for c in cells
            if c.system_building_element == StructureElement.WALL}


def _partition_body(hall, chamber):
    """Shared-column cells bounded on all 4 sides — the interior partition."""
    shared = hall.get_footprint() & chamber.get_footprint()
    union = hall.get_footprint() | chamber.get_footprint()
    return {(x, y) for x, y in shared
            if all((x + dx, y + dy) in union for dx, dy in _NEIGHBOURS)}


def _split(cells):
    """(geometry, materials) — geometry drops only ``system_material``."""
    geometry, materials = {}, {}
    for c in cells:
        data = asdict(c)
        materials[(c.x, c.y, c.z)] = data.pop("system_material")
        geometry[(c.x, c.y, c.z)] = data
    return geometry, materials


class WallMaterialBaselineTests(unittest.TestCase):
    """Today the writer applies one building material to every wall cell."""

    def test_writer_ignores_room_wall_material(self):
        a = room("a", x=0, y=0, width=7, depth=5)            # stone
        b = room("b", x=6, y=0, width=7, depth=5)            # shares x=6 column
        b.wall_material = "wood"
        shared = a.get_footprint() & b.get_footprint()
        self.assertTrue(shared)

        walls = pass3_interior_walls([a, b], [], 0, "world", "bld", "iron")
        xy = [(c.x, c.y) for c in walls]
        self.assertEqual(len(xy), len(set(xy)))              # one cell per coord
        self.assertLessEqual(shared, {(c.x, c.y) for c in walls})
        self.assertEqual({c.system_material for c in walls}, {"iron"})

        a.wall_material, b.wall_material = "crystal", "iron"  # any values
        again = pass3_interior_walls([a, b], [], 0, "world", "bld", "iron")
        self.assertEqual({(c.x, c.y): c.system_material for c in walls},
                         {(c.x, c.y): c.system_material for c in again})

    def test_concave_t_shape_perimeter_is_uniform(self):
        t = room("t", x=0, y=0, width=7, depth=3)
        t.shape_type = "t_shape"
        t.shape_params = {"stem_width": 2, "stem_wall": "south"}
        footprint = t.get_footprint()
        xs = [x for x, _ in footprint]
        ys = [y for _, y in footprint]
        bbox = {(x, y) for x in range(min(xs), max(xs) + 1)
                for y in range(min(ys), max(ys) + 1)}
        notch = bbox - footprint
        self.assertTrue(notch)                                # concave footprint

        walls = pass3_interior_walls([t], [], 0, "world", "bld", "iron")
        self.assertEqual({(c.x, c.y) for c in walls},
                         footprint - _interior(footprint))
        self.assertEqual({c.system_material for c in walls}, {"iron"})
        niche_walls = {(c.x, c.y) for c in walls
                       if any((c.x + dx, c.y + dy) in notch
                              for dx, dy in _NEIGHBOURS)}
        self.assertTrue(niche_walls)                          # niche cells are walls today

    def test_open_shaft_drops_partitions_closed_keeps_them_uniform(self):
        runs = {}
        for has_walls in (False, True):
            host = room("host", x=0, y=0, width=15, depth=15)
            shaft = room("shaft", x=5, y=5, width=5, depth=5)  # fully interior
            shaft.is_shaft = True
            shaft.shaft_has_walls = has_walls
            shaft.embedded_host_key = host.uid_key
            walls = pass3_interior_walls([host, shaft], [], 0, "world", "bld", "iron")
            runs[has_walls] = walls
            self.assertEqual({c.system_material for c in walls}, {"iron"})
            shaft_perim = shaft.get_footprint() - _interior(shaft.get_footprint())
            self.assertEqual(bool({(c.x, c.y) for c in walls} & shaft_perim), has_walls)
        self.assertLess({(c.x, c.y) for c in runs[False]},
                        {(c.x, c.y) for c in runs[True]})

    def test_z_layers_repeat_same_wall_geometry_and_material(self):
        a = room("a", x=0, y=0, width=7, depth=5)              # floor wood
        b = room("b", x=6, y=0, width=7, depth=5)
        b.wall_material = "stone"
        b.floor_material = "stone"
        uids = {a.uid_key: "room-a", b.uid_key: "room-b"}
        cells = build_level_cells([a, b], [], 0, 3, "world", "bld", "iron", uids)

        walls = _walls(cells)
        self.assertEqual({z for _, _, z in walls}, {0, 1, 2})
        per_z = {z: {(x, y) for x, y, zz in walls if zz == z} for z in (0, 1, 2)}
        self.assertEqual(per_z[0], per_z[1])
        self.assertEqual(per_z[1], per_z[2])
        self.assertEqual({c.system_material for c in walls.values()}, {"iron"})

        floors = [c for c in cells
                  if c.system_building_element == StructureElement.FLOOR]
        self.assertEqual({c.z for c in floors}, {0})
        by_room = {}
        for c in floors:
            by_room.setdefault(c.location_uid, set()).add(c.system_material)
        self.assertEqual(by_room, {"room-a": {"wood"}, "room-b": {"stone"}})

    @staticmethod
    def _two_room_template():
        return StructureTemplate(
            system_name=_BASELINE_TEMPLATE_ID,
            display_name="WallBaseline",
            default_z_height=4,
            levels=[level_wire(rooms=[
                room_wire(room_id="hall", display_name="Hall", economic_tier="basic",
                          size={"width_range": [9, 9], "depth_range": [7, 7]},
                          entry_point={"wall": "south",
                                       "passage_type": "main_entrance"}),
                room_wire(room_id="chamber", display_name="Chamber",
                          economic_tier="standard",
                          size={"width_range": [7, 7], "depth_range": [7, 7]}),
            ])],
            connections=[dict(from_room="hall", to_room="chamber",
                              passage_type="doorway")],
        )

    def test_full_generation_partition_room_material_shell_building_material(self):
        # Post-S6 contract: exterior shell → building material; the shared
        # partition is decided by the §11 policy layer (default building
        # band WEALTHY → min strength → oak).
        world, building = test_world_building()
        world.material_registry = _WORLD_MATERIALS
        building.parent_wall_material = "iron"
        probe = RotationProbe()
        first = probe.generate_from_template(world, building, self._two_room_template())
        rooms = {r.room_id: r
                 for r in probe.runtime_rooms if not r.is_shaft}
        room_materials = {key: r.wall_material for key, r in rooms.items()}
        self.assertEqual(room_materials, {"hall": "oak", "chamber": "granite"})

        walls = _walls(first.cells)
        self.assertTrue(walls)
        body = _partition_body(rooms["hall"], rooms["chamber"])
        self.assertTrue(body)
        for (x, y, z), cell in walls.items():
            expected = "oak" if (x, y) in body else "iron"
            self.assertEqual(cell.system_material, expected, (x, y, z))

        doors = [c for c in first.cells
                 if c.system_building_element == StructureElement.DOOR]
        self.assertTrue(doors)
        self.assertEqual({c.system_material for c in doors}, {"oak"})

        floor_mats = {c.system_material for c in first.cells
                      if c.system_building_element == StructureElement.FLOOR}
        self.assertEqual(floor_mats, {"oak", "granite"})

        second = RotationProbe().generate_from_template(
            world, building, self._two_room_template())
        self.assertEqual((first.cells, first.passages),
                         (second.cells, second.passages))

    def test_rotation_preserves_material_assignment(self):
        world, building = test_world_building()
        world.material_registry = _WORLD_MATERIALS
        building.parent_wall_material = "iron"
        base_probe = RotationProbe()
        base = base_probe.generate_from_template(
            world, building, self._two_room_template())
        _, base_mats = _split(base.cells)
        for facing in sorted(CARDINAL_FACINGS):
            with self.subTest(facing=facing):
                probe = RotationProbe()
                actual = probe.generate_from_template(
                    world, building, self._two_room_template(), facing=facing)
                orientation = entry_orientation(
                    base_probe.runtime_rooms, base.passages,
                    _BASELINE_TEMPLATE_ID, facing)
                expected = {
                    (*rotate_point((x, y), orientation.pivot,
                                   orientation.quarter_turns), z): m
                    for (x, y, z), m in base_mats.items()
                }
                _, actual_mats = _split(actual.cells)
                self.assertEqual(expected, actual_mats)

    def test_embedded_shaft_uniform_material_across_flag_and_seeds(self):
        world, _ = test_world_building()
        for has_walls in (False, True):
            for uid in ("wall-baseline-a", "wall-baseline-b"):
                with self.subTest(has_walls=has_walls, building=uid):
                    building = NamedLocation(
                        location_uid=uid, world_uid=world.world_uid,
                        display_name="B", system_location_type="building",
                        created_at="2026-09-29", map_x=23, map_y=-17, map_z=7)
                    template = test_embedded_shaft.EmbeddedShaftTests().template(
                        "north_east")
                    template.staircases[0]["has_walls"] = has_walls
                    first = RotationProbe().generate_from_template(
                        world, building, template)
                    second = RotationProbe().generate_from_template(
                        world, building, template)
                    self.assertEqual((first.cells, first.passages),
                                     (second.cells, second.passages))
                    walls = _walls(first.cells)
                    self.assertTrue(walls)
                    self.assertEqual(
                        {c.system_material for c in walls.values()},
                        {DEFAULT_WALL_MATERIAL})
