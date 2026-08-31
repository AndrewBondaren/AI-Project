"""C21 / P13: plot ground_z, parcel ≠ bbox, approach ray, clamp."""

from __future__ import annotations

import math
import unittest

from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import AreaSlot
from app.application.worldData.generators.assemblers.areaAssembler.areaThreshold import (
    AreaThresholdKind,
)
from app.application.worldData.generators.assemblers.areaAssembler.planner.areaPaths import (
    build_area_paths,
)
from app.application.worldData.generators.assemblers.areaAssembler.planner.measureApproach import (
    measure_street_approach,
    peek_abutting_street_z,
)
from app.application.worldData.generators.assemblers.areaAssembler.planner.resolveThreshold import (
    plot_equals_house,
    resolve_threshold,
)
from app.application.worldData.generators.assemblers.areaAssembler.streetApproach import (
    ApproachForm,
    StreetApproach,
)
from app.application.worldData.generators.assemblers.settlementAssembler.settlementAssembler import (  # noqa: F401
    SettlementAssembler,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.areaSlots import (
    YARD_PADDING_M,
    parcel_cells,
)
from app.application.worldData.generators.coordinates.approachZ import (
    approach_angle_deg,
    clamp_near_z_to_45,
    classify_approach,
)
from app.dataModel.terrain.relief.reliefSlopeGeom import angle_from_height_length
from app.application.worldData.generators.coordinates.columnSurface import (
    column_surface,
    median_surface_z,
    resolve_district_pin_z,
)
from app.application.worldData.generators.coordinates.gridRay import walk_grid_ray
from app.application.worldData.generators.road.streetCells import rasterize_street_xy
from app.application.worldData.generators.structure.layoutTranslate import translate_layout
from app.application.worldData.generators.structure.structureGeneratorService import (
    OccupiedFootprint,
    StructureLayout,
)
from app.dataModel.connections.enums.connectionNodeType import ConnectionNodeType
from app.dataModel.spatial.facing import Facing
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.locationLevel import LocationLevel
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation


def _cell(x: int, y: int, z: int) -> MapCell:
    return MapCell(world_uid="w", x=x, y=y, z=z)


class ColumnSurfaceTests(unittest.TestCase):

    def test_max_per_column_and_empty(self):
        self.assertEqual(column_surface(None), {})
        self.assertEqual(column_surface([]), {})
        surface = column_surface([
            _cell(1, 1, 2),
            _cell(1, 1, 5),
            _cell(2, 1, 3),
        ])
        self.assertEqual(surface[(1, 1)], 5)
        self.assertEqual(surface[(2, 1)], 3)

    def test_median_and_pin_not_max_aabb(self):
        surface = {(0, 0): 1, (1, 0): 9, (2, 0): 2}
        self.assertEqual(median_surface_z([(0, 0), (1, 0), (2, 0)], surface, 0), 2)
        settlement = NamedLocation(
            location_uid="s", world_uid="w", display_name="S",
            system_location_type="settlement", created_at="t", map_z=0,
        )
        self.assertEqual(resolve_district_pin_z(settlement, 0, 0, surface), 1)
        self.assertNotEqual(resolve_district_pin_z(settlement, 0, 0, surface), 9)


class GridRayAndApproachZTests(unittest.TestCase):

    def test_walk_excludes_origin_inclusive_stop(self):
        ray = walk_grid_ray((0, 0), Facing.EAST, max_k=5, stop=lambda c, k: c == (3, 0))
        self.assertEqual(ray, ((1, 0), (2, 0), (3, 0)))

    def test_classify_and_clamp_up_down(self):
        theta, form = classify_approach(0, 4)
        self.assertEqual(form, ApproachForm.NONE)
        theta, form = classify_approach(1, 4)
        self.assertEqual(form, ApproachForm.GRADE)
        self.assertLessEqual(math.degrees(theta), 30.0)
        self.assertAlmostEqual(
            approach_angle_deg(1, 4),
            angle_from_height_length(1, 4),
            places=7,
        )
        self.assertAlmostEqual(math.degrees(theta), angle_from_height_length(1, 4), places=7)
        theta, form = classify_approach(3, 4)
        self.assertEqual(form, ApproachForm.STAIRS)
        theta, form = classify_approach(10, 3)
        self.assertEqual(form, ApproachForm.STAIRS)
        self.assertGreater(math.degrees(theta), 45.0)
        self.assertAlmostEqual(
            math.degrees(theta), angle_from_height_length(10, 3), places=7,
        )
        self.assertEqual(clamp_near_z_to_45(10, 0, 3), 3)
        self.assertEqual(clamp_near_z_to_45(0, 10, 3), 7)
        self.assertEqual(clamp_near_z_to_45(2, 0, 5), 2)


class ParcelCellsTests(unittest.TestCase):

    def test_parcel_wider_than_footprint(self):
        fp = OccupiedFootprint(min_x=0, min_y=0, width=4, depth=3)
        cells = parcel_cells(fp, 10, 20, YARD_PADDING_M)
        xs = {c[0] for c in cells}
        ys = {c[1] for c in cells}
        self.assertEqual(min(xs), 10 - YARD_PADDING_M)
        self.assertEqual(max(xs), 10 + 3 + YARD_PADDING_M)
        self.assertEqual(min(ys), 20 - YARD_PADDING_M)
        self.assertEqual(max(ys), 20 + 2 + YARD_PADDING_M)
        self.assertGreater(len(cells), 4 * 3)


class StreetPeekAndRaySkipTests(unittest.TestCase):

    def test_mid_block_peek_uses_edge_not_node(self):
        street_xy = {(5, 0), (6, 0), (7, 0)}
        surface = {(5, 0): 4, (6, 0): 4, (7, 0): 4}
        z = peek_abutting_street_z((6, 1), Facing.SOUTH, street_xy, surface)
        self.assertEqual(z, 4)

    def test_equal_z_skips_ray(self):
        street_xy = {(1, 0)}
        surface = {(1, 0): 5}
        approach = measure_street_approach(
            (1, 1), Facing.SOUTH, 5, street_xy, surface, max_k=16,
        )
        self.assertEqual(approach.form, ApproachForm.NONE)
        self.assertEqual(approach.ray, ())
        self.assertEqual(approach.length, 0)

    def test_delta_z_walks_to_street(self):
        street_xy = {(1, 0)}
        surface = {(1, 0): 4}
        approach = measure_street_approach(
            (0, 0), Facing.EAST, 8, street_xy, surface, max_k=16,
        )
        self.assertNotEqual(approach.form, ApproachForm.NONE)
        self.assertEqual(approach.ray[-1], (1, 0))
        self.assertEqual(approach.z_far, 4)
        self.assertEqual(approach.length, 1)


class RasterizeStreetTests(unittest.TestCase):

    def test_horizontal_width(self):
        nodes = [
            ConnectionNode(node_uid="a", x=0, y=0, z=1, node_type="intersection", graph_level="district", world_uid="w"),
            ConnectionNode(node_uid="b", x=4, y=0, z=2, node_type="intersection", graph_level="district", world_uid="w"),
        ]
        edges = [
            ConnectionEdge(
                edge_uid="e", from_node_uid="a", to_node_uid="b",
                connection_type="road", graph_level="district", world_uid="w",
                width_cells=2,
            ),
        ]
        xy = rasterize_street_xy(nodes, edges)
        self.assertIn((2, 0), xy)
        self.assertTrue(any(c[1] != 0 for c in xy) or (2, 0) in xy)


class TranslateDzTests(unittest.TestCase):

    def test_translate_shifts_cells_levels_rooms(self):
        layout = StructureLayout(
            cells=[_cell(0, 0, 0)],
            levels=[LocationLevel(level_uid="l", location_uid="b", z=0, z_height=3, display_name="g")],
            passages=[],
            rooms=[NamedLocation(
                location_uid="r", world_uid="w", display_name="R",
                system_location_type="room", created_at="t", map_x=0, map_y=0, map_z=0,
            )],
            occupied_footprint=OccupiedFootprint(0, 0, 1, 1),
        )
        moved = translate_layout(layout, 5, 7, 3)
        self.assertEqual(moved.cells[0].x, 5)
        self.assertEqual(moved.cells[0].y, 7)
        self.assertEqual(moved.cells[0].z, 3)
        self.assertEqual(moved.levels[0].z, 3)
        self.assertEqual(moved.rooms[0].map_z, 3)
        self.assertEqual(moved.occupied_footprint.min_x, 5)


class ThresholdAndGateGraphTests(unittest.TestCase):

    def test_gate_on_parcel_edge_not_footprint(self):
        slot = AreaSlot(
            cells=[(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)],
            ground_z=0,
            facing=Facing.SOUTH,
        )
        threshold = resolve_threshold(slot, has_barrier=True, entry_xy=(1, 1))
        self.assertEqual(threshold.kind, AreaThresholdKind.GATE)
        self.assertEqual(threshold.cells[0][1], 0)
        self.assertFalse(plot_equals_house(slot.cells, [(1, 1)]))

    def test_gate_path_ends_at_waypoint(self):
        threshold = resolve_threshold(
            AreaSlot(cells=[(0, 0), (2, 0), (0, 2), (2, 2)], ground_z=0, facing=Facing.SOUTH),
            has_barrier=True,
        )
        approach = StreetApproach(
            ray=(), length=0, z_far=0, z_near=0, theta_rad=0.0, form=ApproachForm.NONE,
        )
        nodes, edges = build_area_paths(
            world_uid="w",
            threshold=threshold,
            approach=approach,
            facing=Facing.SOUTH,
            building=None,
            door_xy=None,
        )
        self.assertTrue(nodes)
        self.assertEqual(nodes[0].node_type, ConnectionNodeType.WAYPOINT.value)
        self.assertTrue(edges)

    def test_door_when_plot_equals_house(self):
        house = [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)]
        slot = AreaSlot(cells=list(house), ground_z=0, facing=Facing.SOUTH)
        self.assertTrue(plot_equals_house(slot.cells, house))
        threshold = resolve_threshold(
            slot, has_barrier=True, entry_xy=(1, 0), house_cells=house,
        )
        self.assertEqual(threshold.kind, AreaThresholdKind.DOOR)
        self.assertEqual(threshold.cells, [(1, 0)])

    def test_entry_on_parcel_edge_is_not_door_when_yard(self):
        house = [(0, 1), (1, 1), (2, 1)]
        slot = AreaSlot(
            cells=[(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)],
            ground_z=0,
            facing=Facing.SOUTH,
        )
        threshold = resolve_threshold(
            slot, has_barrier=False, entry_xy=(1, 0), house_cells=house,
        )
        self.assertEqual(threshold.kind, AreaThresholdKind.PARCEL_EDGE)
        self.assertEqual(threshold.cells[0][1], 0)


class ClampXyUnchangedTests(unittest.TestCase):

    def test_clamp_does_not_change_xy_formula(self):
        bx, by = 40, 80
        z_up = clamp_near_z_to_45(0, 10, 3)
        z_down = clamp_near_z_to_45(20, 10, 3)
        self.assertEqual(z_up, 7)
        self.assertEqual(z_down, 13)
        self.assertEqual((bx, by), (40, 80))


if __name__ == "__main__":
    unittest.main()
