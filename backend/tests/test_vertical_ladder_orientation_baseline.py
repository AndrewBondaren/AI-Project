"""S2: fixed internal/external ladder author-frame anchors and cells."""
import unittest

from tests.test_u_shape_orientation_baseline import room
from app.application.worldData.generators.structure.staircase.verticalLadder.verticalLadder import VerticalLadderBuilder
from app.application.worldData.generators.structure.staircase.verticalLadder.externalVerticalLadder import ExternalVerticalLadderBuilder
from app.dataModel.structure.building.staircaseSpec import StaircaseSpec
from app.dataModel.structure.enums.staircaseType import StaircaseType
from app.db.models.locationLevel import LocationLevel
from app.db.models.mapCell import MapCell


class VerticalLadderBaselineTests(unittest.TestCase):
    def build(self, builder_type=VerticalLadderBuilder, reverse=False, **entry):
        low, high = room("low"), room("high", z=1)
        levels = [LocationLevel("low", "b", 0, 3, "Low"), LocationLevel("high", "b", 3, 3, "High")]
        cells = {(x,y,z): MapCell("w", x,y,z, system_building_element="floor")
                 for z in (0,3) for x in range(10,17) for y in range(20,27)}
        args = (high, low, levels[1], levels[0]) if reverse else (low, high, *levels)
        spec = StaircaseSpec.model_validate({"stops": ["low", "high"], **entry})
        builder = builder_type(*args, cells, "w", "b", "wood", "ladder", sc_entry=spec, passage_height=2)
        anchors = builder.build()
        return builder, anchors, cells

    def test_fixed_internal_near_wall_trapdoor_and_level_order(self):
        for near_wall in (False, True):
            for trapdoor in (False, True):
                first, anchors, cells = self.build(near_wall=near_wall, has_trapdoor=trapdoor)
                reverse, reverse_anchors, reverse_cells = self.build(reverse=True, near_wall=near_wall, has_trapdoor=trapdoor)
                self.assertEqual(anchors, ((11,21), (11,21)))
                self.assertEqual(anchors, reverse_anchors)
                self.assertEqual(cells, reverse_cells)
                self.assertEqual((first.z_lo, first.z_top), (reverse.z_lo, reverse.z_top))
                self.assertEqual({p for p in first.path_set}, {(11,21,z) for z in range(3)})
                self.assertTrue(all(cells[(11,21,z)].system_building_element == "ladder" for z in range(3)))
                self.assertEqual(cells[(11,21,3)].system_building_element, "trapdoor" if trapdoor else "floor")

    def test_fixed_external_and_on_edge_share_anchor(self):
        internal, a, _ = self.build(on_the_edge=True, facing="north")
        external, b, _ = self.build(ExternalVerticalLadderBuilder, facing="north")
        self.assertEqual(a, b)
        self.assertEqual(a[0], a[1])
        self.assertEqual(a[0][1], 27)
        self.assertTrue(10 < a[0][0] < 16)
        self.assertEqual(internal.path_set, external.path_set)

    def test_trapdoor_alias_is_vertical_ladder(self):
        self.assertEqual(StaircaseType.parse_template("trapdoor"), StaircaseType.VERTICAL_LADDER)
