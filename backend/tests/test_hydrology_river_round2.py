"""Round 2: identity, per-object errors, proven confluences and fallback facts."""

from dataclasses import replace
from types import SimpleNamespace
import json
import unittest
from unittest.mock import patch

from app.application.jsonValidation.resolve import ResolveContext
from app.application.worldData.generators.coordinates.space import CoordinateSpace as Space
from app.application.worldData.generators.hydrology.riverNetworkAssembler import assemble_rivers
from app.application.worldData.generators.hydrology.rivers.riverPrepare import prepare_river
from app.application.worldData.generators.hydrology.rivers.riverRouteRequests import request_from_segments
from app.application.worldData.generators.hydrology.shore.fineHydrologyIndex import apply_declared_fine_river_carves
from app.application.worldData.generators.hydrology.types import DeclaredRiverEdge, RiverSegment
from app.dataModel.hydrology.declaredRiver import DeclaredRiver
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole as Role
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType as Connection
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology, dump_cell_hydrology, parse_cell_hydrology
from app.dataModel.hydrology.riverDrainageLink import RiverDrainageLink
from app.dataModel.hydrology.riverRouting import RiverRouteDiagnostic, RiverRoutingCode as Code, RiverRoutingFailure as Failure
from app.dataModel.hydrology.rivers import HydrologyRiversPolicy
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from tests.hydrology_fixtures import flat_heightmap, hydro_topology, hydro_master, hydro_world, named_location
from tests.test_hydrology_river_routing import edge, water, world


class Round2RiverTests(unittest.TestCase):
    def assemble(self, hm, edges=(), intents=(), occupied=None, locations=(), ctx=None, bodies=()):
        return assemble_rivers(world(), hm, hydro_master(declared_river_edges=list(edges),
            declared_river_intents=list(intents)), occupied or {}, locations,
            topology=hydro_topology(hm), water_bodies=bodies, ctx=ctx or ResolveContext(validate_only=True))

    def test_location_uid_is_not_receiving_body_uid(self):
        for mouth_x in (4, 3):
            with self.subTest(mouth_x=mouth_x):
                hm = flat_heightmap(0, 5, 0, 0, z=10)
                hm.surface_z[(4, 0)] = -2
                intent = DeclaredRiver(location_uid="river", declare_mode="endpoints",
                    source={"x": 0, "y": 0}, mouth={"location_uid": "lake-location"})
                result = self.assemble(hm, intents=[intent], occupied={(4, 0): water("auto-lake")},
                    locations=[named_location("lake-location", mouth_x, 0)])
                self.assertEqual(result.diagnostics, ())
                self.assertEqual(result.segments[0].polyline_cells[-1], (4, 0))
                self.assertEqual(result.drainage_links[0].receiver_uid, "auto-lake")

    def test_roleless_water_uses_real_elevation_and_body_metadata(self):
        hm = flat_heightmap(0, 4, 0, 0, z=10)
        hm.surface_z[(4, 0)] = -2
        occupied = {(4, 0): MapCellHydrology(water_body_uid="auto", z_water_level=0)}
        body = WaterBody(water_body_uid="auto", location_uid="location", kind=BasinKind.LAKE,
                         declared_level=0, z_water_level=0)
        request = request_from_segments(world(), [RiverSegment(list(hm.surface_z), "river", location_uid="r")],
            occupied, hm.surface_z, space=Space.WORLD_FINE_GRID)
        self.assertEqual(request.requested_receiver_uid, "auto")
        self.assertIsNone(request.requested_mouth.location_uid)
        result = self.assemble(hm, edges=[edge("r", (0, 0), (4, 0))], occupied=occupied, bodies=[body])
        self.assertEqual(result.diagnostics, ())
        self.assertEqual(result.drainage_links[0].receiver_kind, BasinKind.LAKE)

    def test_redirect_preserves_authored_location_and_resolved_original_body(self):
        hm = flat_heightmap(0, 6, 0, 4, z=50)
        hm.surface_z.update({(1, 3): 20, (1, 2): 10, (1, 1): -2, (5, 3): -2})
        intent = DeclaredRiver(location_uid="r", declare_mode="endpoints", source={"x": 1, "y": 3},
                               mouth={"location_uid": "original-location"})
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING"):
            result = self.assemble(hm, intents=[intent], locations=[named_location("original-location", 5, 3)],
                occupied={(1, 1): water("alternate"), (5, 3): water("auto-original")}, ctx=ResolveContext())
        fact = result.diagnostics[0]
        self.assertEqual(fact.requested_mouth.location_uid, "original-location")
        self.assertEqual(fact.requested_receiver_uid, "auto-original")
        self.assertEqual(fact.receiver_uid, "alternate")

    def test_invalid_type_on_second_segment_is_atomic_and_other_object_continues(self):
        hm = flat_heightmap(0, 4, 0, 2, z=10)
        hm.surface_z[(4, 2)] = -2
        before = dict(hm.surface_z)
        bad = DeclaredRiverEdge("bad-edge", ((2, 0), (4, 0)), "not-a-river", location_uid="bad")
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING") as logged:
            result = self.assemble(hm, edges=[edge("bad", (0, 0), (2, 0)), bad,
                edge("good", (0, 2), (4, 2))], occupied={(4, 2): water("lake")}, ctx=ResolveContext())
        self.assertEqual({s.location_uid for s in result.segments}, {"good"})
        self.assertTrue(all(hm.surface_z[(x, 0)] == before[(x, 0)] for x in range(5)))
        fact = result.diagnostics[0]
        self.assertIs(fact.code, Code.INVALID_CONNECTION_TYPE)
        self.assertIsNone(fact.object_type)
        self.assertEqual(fact.rejected_connection_type, "not-a-river")
        payload = json.loads(logged.records[0].getMessage().rsplit(" | ", 1)[1])
        self.assertEqual(RiverRouteDiagnostic.model_validate(payload), fact)

    def test_invalid_type_rechecked_at_profile_boundary(self):
        hm = flat_heightmap(0, 3, 0, 0, z=10)
        hm.surface_z[(3, 0)] = -2
        occupied = {(3, 0): water("lake")}
        request = request_from_segments(world(), [RiverSegment(list(hm.surface_z), "river", location_uid="r")],
            occupied, hm.surface_z, space=Space.WORLD_FINE_GRID)
        request = replace(request, segments=(replace(request.segments[0], connection_type="invalid"),))
        before = dict(hm.surface_z)
        job = prepare_river(world(), hm, request, occupied, hydro_topology(hm), HydrologyRiversPolicy(), (),
            ResolveContext(), 0, space=Space.WORLD_FINE_GRID)
        self.assertEqual(job.specs, ())
        self.assertIs(job.diagnostics[0].code, Code.INVALID_CONNECTION_TYPE)
        self.assertEqual(hm.surface_z, before)

    def test_foreign_bed_source_is_invalid_source_without_search(self):
        hm = flat_heightmap(0, 3, 0, 0, z=10)
        occupied = {(0, 0): MapCellHydrology(role=Role.RIVER_BED, water_body_uid="other"),
                    (3, 0): water("lake")}
        with patch("app.application.worldData.generators.hydrology.rivers.riverPrepare.fallback_route") as search:
            result = self.assemble(hm, edges=[edge("r", (0, 0), (3, 0))], occupied=occupied)
        self.assertIs(result.diagnostics[0].code, Code.INVALID_SOURCE)
        self.assertIs(result.diagnostics[0].reason, Failure.BLOCKED)
        search.assert_not_called()

    def test_missing_source_location_retains_missing_anchor(self):
        hm = flat_heightmap(0, 4, 0, 0, z=10)
        intent = DeclaredRiver(location_uid="r", declare_mode="via_locations",
                               route_location_uids=["missing-source", "end"])
        result = self.assemble(hm, intents=[intent], locations=[named_location("end", 4, 0)])
        self.assertIs(result.diagnostics[0].reason, Failure.MISSING_ANCHOR)

    def metadata_case(self, *, reachable=True, alternative=False):
        hm = flat_heightmap(0, 4, 0, 3, z=50)
        hm.surface_z.update({(0, 0): 10, (0, 1): 10, (0, 2): -2})
        occupied = {(0, 2): MapCellHydrology(role=Role.LAKE, z_water_level=0)}
        if not reachable:
            hm.surface_z[(0, 1)] = 50
        if alternative:
            hm.surface_z.update({(1, 0): 10, (2, 0): -2})
            occupied[(2, 0)] = water("valid")
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING") as logged:
            result = self.assemble(hm, edges=[edge("r", (0, 0), (4, 3))], occupied=occupied,
                                   ctx=ResolveContext())
        return result, logged

    def test_reachable_missing_metadata_is_reported_without_losing_original_failure(self):
        result, logged = self.metadata_case()
        fact = result.diagnostics[0]
        self.assertIs(fact.reason, Failure.UPHILL)
        self.assertIs(fact.fallback_reason, Failure.RECEIVER_METADATA)
        self.assertIs(fact.code, Code.NO_REACHABLE_WATER)
        self.assertEqual(len(logged.records), 1)

    def test_unreachable_metadata_candidate_does_not_set_metadata_failure(self):
        result, _ = self.metadata_case(reachable=False)
        self.assertIsNone(result.diagnostics[0].fallback_reason)

    def test_valid_alternative_wins_without_candidate_logs(self):
        result, logged = self.metadata_case(alternative=True)
        self.assertIs(result.diagnostics[0].code, Code.REDIRECTED)
        self.assertEqual(result.diagnostics[0].receiver_uid, "valid")
        self.assertIsNone(result.diagnostics[0].fallback_reason)
        self.assertEqual(len(logged.records), 1)

    def network(self, reverse=False):
        hm = flat_heightmap(0, 6, 0, 3, z=10)
        hm.surface_z[(6, 0)] = -2
        edges = [edge("stem", (0, 0), (6, 0)), edge("tributary", (2, 2), (2, 0)),
                 edge("small", (0, 2), (2, 2))]
        if reverse:
            edges.reverse()
        result = self.assemble(hm, edges=edges, occupied={(6, 0): water("lake")})
        return hm, result

    def test_river_to_river_to_basin_order_independent_and_receiver_floor_preserved(self):
        outputs = []
        for reverse in (False, True):
            hm, result = self.network(reverse)
            self.assertEqual(result.diagnostics, ())
            self.assertEqual({s.location_uid for s in result.segments}, {"stem", "tributary", "small"})
            links = {link.river_uid: link for link in result.drainage_links}
            self.assertEqual(links["tributary"].receiver_uid, "stem")
            self.assertIs(links["tributary"].receiver_kind, Connection.RIVER)
            self.assertEqual(links["small"].receiver_uid, "tributary")
            self.assertEqual(links["stem"].receiver_uid, "lake")
            self.assertEqual(hm.surface_z[(2, 0)], 7)
            self.assertEqual(result.by_cell[(2, 0)].water_body_uid, "stem")
            self.assertEqual(result.by_cell[(2, 2)].water_body_uid, "tributary")
            self.assertEqual(parse_cell_hydrology(dump_cell_hydrology(result.by_cell[(0, 2)])),
                             result.by_cell[(0, 2)])
            outputs.append((hm.surface_z, result.by_cell, links))
        self.assertEqual(outputs[0], outputs[1])

    def test_transit_across_confirmed_river_is_blocked(self):
        _, network = self.network()
        hm = flat_heightmap(0, 6, -2, 2, z=10)
        hm.surface_z[(6, -2)] = -2
        occupied = dict(network.by_cell) | {(6, -2): water("lake-2")}
        result = self.assemble(hm, edges=[edge("cross", (4, 2), (4, -2))], occupied=occupied)
        self.assertEqual(result.segments, [])
        self.assertIs(result.diagnostics[0].reason, Failure.BLOCKED)

    def test_cycles_leave_no_profiles_and_independent_river_succeeds(self):
        hm = flat_heightmap(0, 4, 0, 2, z=10)
        hm.surface_z[(4, 2)] = -2
        result = self.assemble(hm, edges=[edge("a", (0, 0), (2, 0)), edge("b", (2, 0), (0, 0)),
            edge("ok", (0, 2), (4, 2))], occupied={(4, 2): water("lake")})
        self.assertEqual({s.location_uid for s in result.segments}, {"ok"})
        self.assertEqual({d.reason for d in result.diagnostics}, {Failure.DRAINAGE_CYCLE})
        self.assertTrue(all(hm.surface_z[(x, 0)] == 10 for x in range(5)))

    def test_failed_tributary_does_not_cancel_stem(self):
        hm = flat_heightmap(0, 6, 0, 2, z=10)
        hm.surface_z.update({(6, 0): -2, (2, 2): 0})
        result = self.assemble(hm, edges=[edge("bad-child", (2, 2), (2, 0)),
            edge("stem", (0, 0), (6, 0))], occupied={(6, 0): water("lake")})
        self.assertEqual({s.location_uid for s in result.segments}, {"stem"})
        self.assertEqual(result.by_cell[(2, 0)].water_body_uid, "stem")

    def test_fallback_can_redirect_to_a_confirmed_river(self):
        hm = flat_heightmap(0, 6, -1, 2, z=10)
        hm.surface_z.update({(6, 0): -2, (2, -1): 50})
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING"):
            result = self.assemble(hm, edges=[edge("stem", (0, 0), (6, 0)),
                edge("child", (2, 2), (2, -1))], occupied={(6, 0): water("lake")}, ctx=ResolveContext())
        fact = result.diagnostics[0]
        self.assertIs(fact.code, Code.REDIRECTED)
        self.assertIs(fact.reason, Failure.BLOCKED)
        self.assertEqual(fact.receiver_uid, "stem")
        self.assertIs(fact.receiver_kind, Connection.RIVER)
        self.assertEqual(result.drainage_links[-1].receiver_uid, "stem")

    def test_fine_confluence_carries_same_drainage_contract(self):
        rivers = [DeclaredRiver(location_uid="stem", declare_mode="segments", segments=[{
            "from": {"x": 0, "y": 0}, "to": {"x": 6, "y": 0}, "connection_type": "river"}]),
            DeclaredRiver(location_uid="child", system_role="tributary", parent_location_uid="stem",
                declare_mode="endpoints", source={"x": 2, "y": 2}, mouth={"location_uid": "stem"})]
        w = hydro_world(fine_cells_per_map_cell=1, hydrology=WorldHydrology(
            default_rivers=HydrologyRiversPolicy(autoresolve=False), declared_rivers=rivers).model_dump(mode="json"))
        hm = flat_heightmap(0, 6, 0, 2, z=10)
        hm.surface_z[(6, 0)] = -2
        ctx = ResolveContext(validate_only=True)
        roles, z = apply_declared_fine_river_carves(w, [named_location("stem", 2, 0)], hm.surface_z,
            topology=hydro_topology(hm), fine_hydro={(6, 0): water("lake")}, ctx=ctx)
        self.assertEqual(ctx.errors, [])
        self.assertEqual(roles[(2, 1)].river_drainage.receiver_uid, "stem")
        self.assertEqual(roles[(2, 0)].water_body_uid, "stem")
        self.assertEqual(z[(2, 0)], 7)

    def test_fine_invalid_type_does_not_abort_other_river(self):
        rivers = [DeclaredRiver(location_uid=uid, declare_mode="segments", segments=[{
            "from": {"x": 0, "y": y}, "to": {"x": 4, "y": y}, "connection_type": kind}])
            for uid, y, kind in (("bad", 0, "bad-kind"), ("good", 2, "river"))]
        w = hydro_world(fine_cells_per_map_cell=1, hydrology=WorldHydrology(
            default_rivers=HydrologyRiversPolicy(autoresolve=False), declared_rivers=rivers).model_dump(mode="json"))
        hm = flat_heightmap(0, 4, 0, 2, z=10)
        hm.surface_z[(4, 2)] = -2
        ctx = ResolveContext(validate_only=True)
        roles, z = apply_declared_fine_river_carves(w, [], hm.surface_z, topology=hydro_topology(hm),
            fine_hydro={(4, 2): water("lake")}, ctx=ctx)
        self.assertEqual(ctx.errors[0].code, Code.INVALID_CONNECTION_TYPE.value)
        self.assertEqual({v.water_body_uid for v in roles.values()}, {"good"})
        self.assertTrue(all(z[(x, 0)] == 10 for x in range(5)))

    def test_coordinate_intent_confluence_is_not_snapped_past_future_river(self):
        hm = flat_heightmap(0, 6, 0, 2, z=10)
        hm.surface_z[(6, 0)] = -2
        child = DeclaredRiver(location_uid="child", declare_mode="endpoints",
            source={"x": 2, "y": 2}, mouth={"x": 2, "y": 0})
        result = self.assemble(hm, edges=[edge("stem", (0, 0), (6, 0))], intents=[child],
            occupied={(6, 0): water("lake")})
        self.assertEqual(result.diagnostics, ())
        self.assertEqual(result.drainage_links[-1].receiver_uid, "stem")
        self.assertEqual(result.segments[-1].polyline_cells[-1], (2, 0))

    def test_external_drainage_cycle_is_not_a_confirmed_receiver(self):
        hm = flat_heightmap(0, 4, 0, 2, z=10)
        links = [RiverDrainageLink(river_uid=uid, river_type=Connection.RIVER,
            receiver_uid=target, receiver_kind=Connection.RIVER, receiver_cell=(x, 0))
            for uid, target, x in (("a", "b", 3), ("b", "a", 2))]
        occupied = {(x, 0): MapCellHydrology(role=Role.RIVER_BED, water_body_uid=link.river_uid,
                    river_drainage=link) for x, link in zip((2, 3), links)}
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING"):
            result = self.assemble(hm, edges=[edge("child", (2, 2), (2, 0))],
                occupied=occupied, ctx=ResolveContext())
        self.assertEqual(result.segments, [])
        self.assertIs(result.diagnostics[0].fallback_reason, Failure.RECEIVER_METADATA)

    def test_planning_requires_explicit_pojo_policy_even_on_empty_terrain(self):
        from app.application.worldData.generators.hydrology.rivers.riverNetworkPlanner import (
            plan_descent_path, plan_path_to_target,
        )
        hm = flat_heightmap(0, 1, 0, 0)
        hm.surface_z.clear()
        topology = hydro_topology(hm)
        for function, args in ((plan_descent_path, (hm, (0, 0), {})),
                               (plan_path_to_target, (hm, (0, 0), (1, 0), {}))):
            with self.subTest(function=function.__name__):
                with self.assertRaises(TypeError):
                    function(*args, topology=topology)
                with self.assertRaises(TypeError):
                    function(*args, topology=topology, policy=None)

    def test_surface_context_rejects_missing_topology_before_relief(self):
        from tests.planning.consumers.test_wiring import Composition, capture, world as source_world
        from app.application.cancellation.requestPlanWait import RequestPlanWait
        from pydantic import ValidationError
        composition = Composition()
        self.addCleanup(composition.service.shutdown)
        view = capture(source_world())
        malformed_water = view.water_placement.model_copy(update={"topology": None})
        malformed = view.model_copy(update={"water_placement": malformed_water})
        with patch.object(composition.registry, "build", wraps=composition.registry.build) as build:
            with self.assertRaises(ValidationError):
                composition.assembler.prepare(malformed, wait=RequestPlanWait.unbounded())
        build.assert_not_called()

    def test_confluence_drop_reads_receiver_final_bed_and_mountain_kind(self):
        hm = flat_heightmap(0, 6, 0, 2, z=20)
        hm.surface_z.update({(6, 0): -2, (2, 1): 30, (2, 2): 40})
        stem = DeclaredRiverEdge("stem-edge", ((0, 0), (6, 0)), "mountain_river", location_uid="stem")
        result = self.assemble(hm, edges=[edge("child", (2, 2), (2, 0)), stem],
            occupied={(6, 0): water("lake")})
        self.assertEqual(result.diagnostics, ())
        self.assertEqual(hm.surface_z[(2, 0)], 16)
        child_link = next(link for link in result.drainage_links if link.river_uid == "child")
        self.assertIs(child_link.receiver_kind, Connection.MOUNTAIN_RIVER)
        drops = [drop for drop in result.drops if drop.connection_edge_uid == "child-edge"]
        self.assertEqual((drops[-1].lower_cell, drops[-1].lower_z), ((2, 0), 16))
