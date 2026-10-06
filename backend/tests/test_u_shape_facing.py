"""B2: upper exterior floors determine far-end and arch-axis orientation."""
import unittest
from copy import deepcopy
from random import Random
from unittest.mock import patch

from app.application.worldData.generators.structure.staircase.uShape.facingResolver import resolve_u_shape_facing
from app.application.worldData.generators.structure.staircase.uShape.uShape import UShapeBuilder
from app.application.worldData.generators.structure.staircase.uShape.uShapeHelper import _compute_u_params
from app.application.worldData.generators.structure.passages.builder import build_transitions
from app.application.worldData.generators.structure.structureGeneratorService import StructureGeneratorService
from app.dataModel.locations.structure.building.staircaseSpec import StaircaseSpec
from app.dataModel.spatial.facing import CARDINAL_WALL_OUTWARD_DELTA, Facing, opposite
from app.dataModel.locations.structure.enums.buildingElement import StructureElement
from app.db.models.mapCell import MapCell
from app.db.models.locationLevel import LocationLevel
from tests.test_u_shape_orientation_baseline import room
from tests.test_structure_orientation import test_world_building
from tests import test_embedded_shaft

BUILDER = "app.application.worldData.generators.structure.passages.builder"
U_SHAPE = "app.application.worldData.generators.structure.staircase.uShape.uShape"


class UShapeFacingTests(unittest.TestCase):
    def floors(self, footprint, side, z=6):
        dx, dy = CARDINAL_WALL_OUTWARD_DELTA[side]
        return {(x + dx, y + dy, z): MapCell("world", x + dx, y + dy, z,
                    system_building_element=StructureElement.FLOOR)
                for x, y in footprint if (x + dx, y + dy) not in footprint}

    def test_unique_score_overrides_authored_facing_in_all_directions(self):
        fp = room(x=0, y=0, width=5, depth=5).get_footprint()
        for side in CARDINAL_WALL_OUTWARD_DELTA:
            cells = self.floors(fp, side)
            self.assertEqual(resolve_u_shape_facing(fp, cells, 6, side), opposite(side))

    def test_zero_score_preserves_fallback_and_counts_only_floor_at_z_top(self):
        fp = room(x=0, y=0, width=5, depth=5).get_footprint()
        cells = self.floors(fp, Facing.EAST, z=5)
        cells.update(self.floors(fp, Facing.WEST))
        for cell in cells.values():
            if cell.z == 6:
                cell.system_building_element = StructureElement.WALL
        cells[(2, 2, 6)] = MapCell("world", 2, 2, 6, system_building_element=StructureElement.FLOOR)
        for fallback in CARDINAL_WALL_OUTWARD_DELTA:
            self.assertEqual(resolve_u_shape_facing(fp, cells, 6, fallback), fallback)

    def test_max_score_and_clockwise_ties_are_deterministic(self):
        fp = room(x=0, y=0, width=5, depth=5).get_footprint()
        cells = self.floors(fp, Facing.EAST)
        south = self.floors(fp, Facing.SOUTH)
        cells.update(dict(list(south.items())[:2]))
        self.assertEqual(resolve_u_shape_facing(fp, cells, 6, Facing.NORTH), Facing.WEST)
        cells.update(south)
        self.assertEqual(resolve_u_shape_facing(fp, cells, 6, Facing.NORTH), Facing.NORTH)
        # Preferred exit NORTH is absent; clockwise from NORTH reaches EAST first.
        self.assertEqual(resolve_u_shape_facing(fp, cells, 6, Facing.SOUTH), Facing.WEST)

    def test_u_builder_passes_detected_facing_to_path_geometry(self):
        shaft = room("shaft", x=0, y=0, width=7, depth=7)
        shaft.is_shaft = True
        shaft.facing = Facing.NORTH
        fr, to = room("hall"), room("upper", z=1)
        low, top = LocationLevel("lo", "building", 0, 6, "Low"), LocationLevel("hi", "building", 6, 6, "Top")
        sc = StaircaseSpec(staircase_id="stairs", stops=["hall", "upper"], facing=Facing.NORTH, has_walls=True)
        cells = self.floors(shaft.get_footprint(), Facing.EAST)
        builder = UShapeBuilder(fr, to, low, top, cells, "world", "building", "stone", "test",
                                shaft=shaft, sc_entry=sc, passage_height=2)
        with patch(U_SHAPE + "._compute_u_params", wraps=_compute_u_params) as compute:
            builder.build()
        self.assertEqual(compute.call_args.args[4], Facing.WEST)
        self.assertTrue(builder.path_set)

    def test_passages_resolve_before_arch_width_and_pass_same_axis_to_stairs(self):
        fr = room("hall", x=0, y=0, width=5, depth=7)
        to = room("upper", x=8, y=0, width=5, depth=7, z=1)
        shaft = room("shaft_lo", x=4, y=0, width=5, depth=7)
        upper_shaft = room("shaft_hi", x=4, y=0, width=5, depth=7, z=1)
        for s in (shaft, upper_shaft):
            s.is_shaft = True
            s.staircase_id = "stairs"
            s.facing = Facing.NORTH
        sc = StaircaseSpec(staircase_id="stairs", stops=["hall", "upper"], facing=Facing.NORTH, has_walls=True)
        levels = {0: LocationLevel("lo", "building", 0, 6, "Low"),
                  1: LocationLevel("hi", "building", 6, 6, "Top")}
        cells = self.floors(shaft.get_footprint(), Facing.EAST)
        with patch(BUILDER + "._build_archway", return_value=None) as arch, \
             patch(BUILDER + ".build_staircase", return_value=(None, None)) as stairs:
            build_transitions(cells, [fr, to, shaft, upper_shaft], [], levels,
                           {"hall": 0, "upper": 1, "shaft_lo": 0, "shaft_hi": 1},
                           "world", "building", Random(1), staircases=[sc])
        self.assertEqual(shaft.facing, Facing.WEST)
        self.assertEqual(upper_shaft.facing, Facing.WEST)
        self.assertEqual(arch.call_count, 2)
        self.assertTrue(all(call.args[0].width == 5 for call in arch.call_args_list))
        self.assertIs(stairs.call_args.kwargs["shaft"], shaft)
        self.assertEqual(sc.facing, Facing.NORTH)

    def test_generate_twice_and_wire_immutability(self):
        template = test_embedded_shaft.EmbeddedShaftTests().template("center", distinct_host=True)
        before = deepcopy(template.model_dump())
        world, building = test_world_building()
        first = StructureGeneratorService().generate_from_template(world, building, template)
        second = StructureGeneratorService().generate_from_template(world, building, template)
        self.assertEqual((first.cells, first.transitions), (second.cells, second.transitions))
        self.assertEqual(template.model_dump(), before)
