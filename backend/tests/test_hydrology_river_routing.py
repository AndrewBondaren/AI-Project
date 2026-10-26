"""Review-debt step 3: atomic rivers, nearest reachable fallback and full facts."""

import json
import unittest

from app.application.jsonValidation.resolve import ResolveContext
from app.application.worldData.generators.hydrology.riverNetworkAssembler import assemble_rivers
from app.application.worldData.generators.hydrology.types import DeclaredRiverEdge
from app.application.worldData.generators.coordinates.space import CoordinateSpace
from app.application.worldData.generators.hydrology.rivers.resolveDeclaredRiverPath import resolve_declared_river_intents
from app.application.worldData.generators.hydrology.load.resolveRiverTypeClassify import resolve_river_type_classify
from app.application.worldData.generators.hydrology.geom.smoothRiverPolyline import step_turn_ok
from app.dataModel.hydrology.declaredRiver import DeclaredRiver, HydrologyMouth
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole as Role
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType as Connection
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.riverRouting import RiverRouteDiagnostic, RiverRoutingCode as Code, RiverRoutingFailure as Failure
from app.dataModel.hydrology.rivers import HydrologyRiversPolicy
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
from tests.hydrology_fixtures import flat_heightmap, hydro_topology, hydro_master, hydro_world, named_location


def world(**policy):
    return hydro_world(fine_cells_per_map_cell=1, hydrology=WorldHydrology(
        default_rivers=HydrologyRiversPolicy(autoresolve=False, **policy)).model_dump(mode="json"))


def water(uid, *, level=0):
    return MapCellHydrology(role=Role.LAKE, water_body_uid=uid, z_water_level=level)


def edge(uid, start, end):
    return DeclaredRiverEdge(uid + "-edge", (start, end), Connection.RIVER.value, location_uid=uid)


class RiverRoutingTests(unittest.TestCase):
    def unreachable_target(self):
        hm = flat_heightmap(0, 6, 0, 4, z=50)
        hm.surface_z.update({(1, 3): 20, (1, 2): 10, (1, 1): -2, (5, 3): -2})
        occupied = {(1, 1): water("alternate"), (5, 3): water("authored")}
        return hm, occupied, hydro_master(declared_river_edges=[edge("named-river", (1, 3), (5, 3))])

    def test_runtime_redirects_to_reachable_water_and_logs_complete_fact(self):
        hm, occupied, master = self.unreachable_target()
        before = dict(hm.surface_z)
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING") as logged:
            result = assemble_rivers(world(), hm, master, occupied, topology=hydro_topology(hm))
        diagnostic = result.diagnostics[0]
        self.assertIs(diagnostic.code, Code.REDIRECTED)
        self.assertIs(diagnostic.reason, Failure.UPHILL)
        self.assertEqual(diagnostic.object_uid, "named-river")
        self.assertIs(diagnostic.object_type, Connection.RIVER)
        self.assertIsNone(diagnostic.requested_mouth.location_uid)
        self.assertEqual(diagnostic.requested_receiver_uid, "authored")
        self.assertEqual((diagnostic.requested_mouth.x, diagnostic.requested_mouth.y), (5, 3))
        self.assertEqual(diagnostic.receiver_uid, "alternate")
        self.assertIs(diagnostic.receiver_kind, BasinKind.LAKE)
        self.assertEqual(diagnostic.receiver_cell, (1, 1))
        self.assertEqual(diagnostic.failure_cell, (2, 3))
        payload = json.loads(logged.records[0].getMessage().rsplit(" | ", 1)[1])
        self.assertEqual(RiverRouteDiagnostic.model_validate(payload), diagnostic)
        self.assertIn("WarningError", logged.records[0].getMessage())
        self.assertEqual(result.segments[0].location_uid, "named-river")
        self.assertEqual(result.segments[0].polyline_cells, [(1, 3), (1, 2), (1, 1)])
        self.assertEqual(hm.surface_z[(1, 1)], before[(1, 1)])
        self.assertEqual(hm.surface_z[(5, 3)], before[(5, 3)])
        self.assertFalse(hasattr(result, "bed_specs"))

    def test_preview_and_import_reject_original_route_without_redirecting(self):
        for ctx in (ResolveContext(validate_only=True), ResolveContext.for_import(validate_only=True),
                    ResolveContext.for_import()):
            with self.subTest(mode=ctx.mode, preview=ctx.validate_only):
                hm, occupied, master = self.unreachable_target()
                before = dict(hm.surface_z)
                result = assemble_rivers(world(), hm, master, occupied, topology=hydro_topology(hm), ctx=ctx)
                self.assertEqual((result.by_cell, result.segments), ({}, []))
                self.assertIs(result.diagnostics[0].code, Code.TARGET_UNREACHABLE)
                self.assertEqual(ctx.errors[0].code, Code.TARGET_UNREACHABLE.value)
                self.assertEqual(hm.surface_z, before)

    def test_no_bodies_is_distinct_and_does_not_leave_a_partial_bed(self):
        hm = flat_heightmap(0, 6, 0, 2, z=20)
        before = dict(hm.surface_z)
        master = hydro_master(declared_river_edges=[edge("dry", (0, 1), (5, 1))])
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING") as logged:
            result = assemble_rivers(world(), hm, master, {}, topology=hydro_topology(hm))
        self.assertIs(result.diagnostics[0].code, Code.NO_WATER_BODIES)
        self.assertIs(result.diagnostics[0].reason, Failure.DRY_MOUTH)
        self.assertIn(Code.NO_WATER_BODIES.value, logged.output[0])
        self.assertEqual((result.by_cell, result.segments, result.drops, result.dirty_bbox), ({}, [], (), None))
        self.assertEqual(hm.surface_z, before)

    def test_existing_but_unreachable_water_is_distinct(self):
        hm = flat_heightmap(0, 6, 0, 4, z=50)
        hm.surface_z.update({(1, 3): 20, (5, 3): -2})
        before = dict(hm.surface_z)
        master = hydro_master(declared_river_edges=[edge("blocked", (1, 3), (5, 3))])
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING"):
            result = assemble_rivers(world(), hm, master, {(5, 3): water("lake")}, topology=hydro_topology(hm))
        self.assertIs(result.diagnostics[0].code, Code.NO_REACHABLE_WATER)
        self.assertEqual(result.by_cell, {})
        self.assertEqual(hm.surface_z, before)

    def test_nearest_unreachable_candidate_does_not_hide_farther_reachable_body(self):
        hm = flat_heightmap(0, 8, 0, 5, z=50)
        hm.surface_z.update({(1, 3): 20, (2, 3): 10, (3, 3): 10,
                             (4, 3): -2, (6, 3): -2})
        master = hydro_master(declared_river_intents=[DeclaredRiver(location_uid="r",
            declare_mode="endpoints", source={"x": 1, "y": 3},
            mouth=HydrologyMouth(location_uid="near-but-isolated"))])
        occupied = {(6, 3): water("near-but-isolated"), (4, 3): water("far-but-reachable")}
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING"):
            result = assemble_rivers(world(), hm, master, occupied,
                [named_location("near-but-isolated", 6, 3)], topology=hydro_topology(hm))
        self.assertIs(result.diagnostics[0].code, Code.REDIRECTED)
        self.assertEqual(result.diagnostics[0].receiver_uid, "far-but-reachable")
        self.assertTrue(result.segments)
        self.assertEqual(result.segments[0].polyline_cells[-1], (4, 3))

    def test_tie_break_is_deterministic_under_input_permutation(self):
        outputs = []
        for reverse in (False, True):
            hm = flat_heightmap(0, 6, 0, 4, z=10)
            hm.surface_z.update({(1, 3): -2, (5, 3): -2})
            cells = [((1, 3), water("left")), ((5, 3), water("right"))]
            occupied = dict(reversed(cells) if reverse else cells)
            if reverse:
                hm.surface_z.clear()
                hm.surface_z.update({(x, y): (-2 if (x, y) in occupied else 10)
                                     for y in reversed(range(5)) for x in reversed(range(7))})
            with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING"):
                result = assemble_rivers(world(), hm, hydro_master(declared_river_edges=[
                    edge("tie", (3, 0), (3, 3))]), occupied, topology=hydro_topology(hm))
            self.assertEqual(result.diagnostics[0].receiver_uid, "left")
            outputs.append((result.segments[0].polyline_cells, result.diagnostics, hm.surface_z))
        self.assertEqual(outputs[0], outputs[1])

    def test_water_floor_does_not_allow_flow_up_to_higher_waterline(self):
        hm = flat_heightmap(0, 3, 0, 0, z=5)
        hm.surface_z[(3, 0)] = -20
        before = dict(hm.surface_z)
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING"):
            result = assemble_rivers(world(), hm, hydro_master(declared_river_edges=[
                edge("low-source", (0, 0), (3, 0))]), {(3, 0): water("high-lake", level=10)},
                topology=hydro_topology(hm))
        self.assertIs(result.diagnostics[0].code, Code.NO_REACHABLE_WATER)
        self.assertIs(result.diagnostics[0].reason, Failure.UPHILL)
        self.assertEqual(hm.surface_z, before)

    def test_multiple_segments_of_one_object_are_atomic(self):
        hm = flat_heightmap(0, 4, 0, 0, z=10)
        hm.surface_z.update({(3, 0): 50, (4, 0): -2})
        before = dict(hm.surface_z)
        master = hydro_master(declared_river_edges=[
            edge("same-river", (0, 0), (2, 0)), edge("same-river", (2, 0), (4, 0))])
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING"):
            result = assemble_rivers(world(), hm, master, {(4, 0): water("lake")}, topology=hydro_topology(hm))
        self.assertEqual((result.by_cell, result.segments), ({}, []))
        self.assertEqual(len(result.diagnostics), 1)
        self.assertEqual(hm.surface_z, before)

    def test_shared_mouth_is_allowed_but_failed_object_does_not_block_independent_river(self):
        hm = flat_heightmap(0, 6, 0, 2, z=20)
        hm.surface_z[(3, 1)] = -2
        master = hydro_master(declared_river_edges=[
            edge("left", (0, 1), (3, 1)), edge("right", (6, 1), (3, 1)),
            edge("invalid", (-1, 0), (3, 1))])
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING"):
            result = assemble_rivers(world(), hm, master, {(3, 1): water("shared")}, topology=hydro_topology(hm))
        self.assertEqual({segment.location_uid for segment in result.segments}, {"left", "right"})
        self.assertEqual(result.diagnostics[0].object_uid, "invalid")
        self.assertIs(result.diagnostics[0].code, Code.INVALID_SOURCE)
        self.assertNotIn((3, 1), result.by_cell)

    def test_missing_mandatory_intent_anchor_is_not_silently_skipped(self):
        hm = flat_heightmap(0, 4, 0, 2, z=20)
        hm.surface_z[(4, 1)] = -2
        river = DeclaredRiver(location_uid="via", declare_mode="via_locations",
            route_location_uids=["source", "missing", "target"])
        locations = [named_location("source", 0, 1), named_location("target", 4, 1)]
        ctx = ResolveContext(validate_only=True)
        result = assemble_rivers(world(), hm, hydro_master(declared_river_intents=[river]),
            {(4, 1): water("target")}, locations, topology=hydro_topology(hm), ctx=ctx)
        self.assertIs(result.diagnostics[0].reason, Failure.MISSING_ANCHOR)
        self.assertEqual(result.segments, [])
        self.assertEqual(result.diagnostics[0].requested_mouth.location_uid, "target")

    def test_wrapped_fallback_crosses_seam(self):
        hm = flat_heightmap(0, 7, 0, 2, z=50)
        hm.surface_z.update({(6, 1): 20, (7, 1): 10, (0, 1): -2})
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING"):
            result = assemble_rivers(world(), hm, hydro_master(declared_river_edges=[
                edge("wrap", (6, 1), (4, 1))]), {(0, 1): water("across-seam")},
                topology=hydro_topology(hm, Mode.WRAPPED))
        self.assertEqual(result.segments[0].polyline_cells, [(6, 1), (7, 1), (0, 1)])
        self.assertIs(result.diagnostics[0].code, Code.REDIRECTED)

    def test_path_limit_comes_from_pojo(self):
        hm = flat_heightmap(0, 4, 0, 0, z=20)
        hm.surface_z[(4, 0)] = -2
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING"):
            result = assemble_rivers(world(max_path_cells=2), hm, hydro_master(declared_river_edges=[
                edge("budget", (0, 0), (4, 0))]), {(4, 0): water("lake")}, topology=hydro_topology(hm))
        self.assertIs(result.diagnostics[0].reason, Failure.PATH_LIMIT)
        self.assertIs(result.diagnostics[0].code, Code.NO_REACHABLE_WATER)

    def test_exact_diagonal_turn_is_allowed_but_right_angle_is_not(self):
        self.assertTrue(step_turn_ok([(0, 0), (1, 0)], (2, 1)))
        self.assertTrue(step_turn_ok([(0, 0), (1, 1)], (1, 2)))
        self.assertFalse(step_turn_ok([(0, 0), (1, 0)], (1, 1)))

    def test_sphere_fallback_crosses_pole(self):
        hm = flat_heightmap(0, 7, 0, 3, z=50)
        hm.surface_z.update({(1, 0): 20, (5, 0): 10, (5, 1): -2})
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING"):
            result = assemble_rivers(world(), hm, hydro_master(declared_river_edges=[
                edge("pole", (1, 0), (2, 2))]), {(5, 1): water("beyond-pole")},
                topology=hydro_topology(hm, Mode.SPHERE))
        self.assertEqual(result.segments[0].polyline_cells, [(1, 0), (5, 0), (5, 1)])
        self.assertEqual(result.diagnostics[0].receiver_uid, "beyond-pole")

    def test_fallback_does_not_invent_receiver_identity(self):
        hm = flat_heightmap(0, 4, 0, 2, z=10)
        hm.surface_z[(0, 2)] = -2
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING"):
            result = assemble_rivers(world(), hm, hydro_master(declared_river_edges=[
                edge("missing-meta", (0, 0), (4, 0))]),
                {(0, 2): MapCellHydrology(role=Role.LAKE, z_water_level=0)}, topology=hydro_topology(hm))
        self.assertEqual(result.segments, [])
        self.assertIs(result.diagnostics[0].code, Code.NO_REACHABLE_WATER)

    def test_mouth_radius_uses_fine_units_in_both_spaces(self):
        for span, space in ((1, CoordinateSpace.WORLD_FINE_GRID),
                            (1000, CoordinateSpace.WORLD_SURFACE_GRID)):
            for radius, expected_end in ((200, 1), (1000, 2)):
                with self.subTest(span=span, radius=radius):
                    w = hydro_world(fine_cells_per_map_cell=span,
                        hydrology=WorldHydrology(default_rivers=HydrologyRiversPolicy(
                            mouth_search_radius_fine=radius)).model_dump(mode="json"))
                    hm = flat_heightmap(0, 3 * 1000 // span, 0, 0, z=10)
                    target = 1000 // span
                    receiver = 2000 // span
                    hm.surface_z[(receiver, 0)] = -2
                    river = DeclaredRiver(location_uid="radius", declare_mode="endpoints",
                        source={"x": 0, "y": 0}, mouth=HydrologyMouth(x=1000, y=0))
                    result = resolve_declared_river_intents(w, hm, [river], [],
                        {(receiver, 0): water("lake")}, resolve_river_type_classify(w),
                        space=space, topology=hydro_topology(hm))
                    self.assertEqual(result[0].polyline_cells[-1], (expected_end * 1000 // span, 0))

    def test_routing_policy_rejects_invalid_limits(self):
        from pydantic import ValidationError
        for field, bad_values in (("mouth_search_radius_fine", (-1, True, 1.5, "200", None)),
                                  ("max_path_cells", (1, True, 1.5, "128", None))):
            for value in bad_values:
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                    HydrologyRiversPolicy.model_validate({field: value})

    def test_coarse_mouth_search_preserves_authored_subcell_position(self):
        w = hydro_world(fine_cells_per_map_cell=1000)
        hm = flat_heightmap(0, 3, 0, 0, z=10)
        hm.surface_z[(2, 0)] = -2
        for mouth_x, expected_end in ((1800, 2), (1799, 1)):
            with self.subTest(mouth_x=mouth_x):
                river = DeclaredRiver(location_uid="subcell", declare_mode="endpoints",
                    source={"x": 0, "y": 0}, mouth=HydrologyMouth(x=mouth_x, y=0))
                result = resolve_declared_river_intents(w, hm, [river], [],
                    {(2, 0): water("lake")}, resolve_river_type_classify(w),
                    space=CoordinateSpace.WORLD_SURFACE_GRID, topology=hydro_topology(hm))
                self.assertEqual(result[0].polyline_cells[-1], (expected_end, 0))


if __name__ == "__main__":
    unittest.main()
