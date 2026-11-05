from copy import replace
from unittest import TestCase
from unittest.mock import patch

from app.encoding.canonicalCodec import encode, decode, digest
from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.hydrology.rivers.planning.coarseRiverPlanner import CoarseRiverPlanner
from app.application.worldData.generators.hydrology.rivers.planning.fine.proposals import procedural_requests
from app.application.worldData.generators.terrain.planning.preWater.terrainBasePlanner import PreWaterTerrainPlanner
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.declaredRiver import DeclaredRiver
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType as Kind
from app.dataModel.hydrology.planning.hydrologyPlan import RiverRoute, RiverPathSegment
from app.dataModel.hydrology.planning.stages.openWaterPlan import OpenWaterPlan
from app.dataModel.hydrology.planning.stages.riverRoutePlans import CoarseRiverPlan, FineRiverPlan
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.riverDrainageLink import RiverDrainageLink
from app.dataModel.hydrology.riverRouting import RiverRouteDiagnostic, RiverRoutingCode, RiverRoutingFailure
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnosticDisposition
from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.topology.topologyGeometry import canonical_neighbors8
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from tests.geo1.fine_water.fixtures import physical_inputs
from tests.geo1.fine_water.test_fill import fill, basin
from tests.geo1.fine_water.test_routing import route, scenario
from tests.geo1.hill_hosts.test_hosts import coverage
from tests.geo1.natural_preparation.fixtures import ReadyPlans
from tests.geo1.terrain_base.fixtures import inputs as terrain_inputs, Control


def native(case, *, wet=True, parent_wet=False):
    values = list(terrain_inputs(mountain=False, hills=False))
    grid = SurfaceGridSettings(fine_span=16, light_side=1)
    values[0], values[1] = replace(values[0], grid=grid), replace(values[1], grid=grid)
    values[2] = replace(values[2], grid=grid, refine_policy=replace(values[2].refine_policy, resample="nearest"))
    heights = {(0, 0): 20, (1, 0): 10, (0, 1): 30, (1, 1): 20}
    terrain = values[4]
    values[4] = replace(terrain, payload=replace(terrain.payload,
        surface_z=tuple((cell, heights[cell.gx, cell.gy]) for cell, _ in terrain.payload.surface_z)))
    ready = ReadyPlans(case, values).build()
    window = PreWaterTerrainPlanner().prepare_window(ready, expected_preparation=ready.ref,
        cells=coverage(0, 32, 0, 32), control=Control())
    physical = physical_inputs(window.payload.topology)
    physical = replace(physical, enabled=True, grid=grid,
        rivers=replace(physical.rivers, enabled=True, autoresolve=True))
    cells = {(24, 8), (25, 8), (24, 9), (25, 9)} if wet else set()
    if parent_wet:
        cells.update({(8, 8), (9, 8), (8, 9), (9, 9)})
    water = fill(window, window.payload.topology, (basin("lake", cells),) if cells else (), physical=physical)
    return physical, water


def proposal(uid, cells, receiver="lake", *, declared=False, kind=Kind.RIVER, span=16):
    path = tuple(SurfaceGridCoord(x, y) for x, y in cells)
    link = RiverDrainageLink(river_uid=uid, river_type=kind, receiver_uid=receiver,
        receiver_kind=BasinKind.LAKE if receiver == "lake" else Kind.RIVER,
        receiver_cell=(path[-1].gx*span, path[-1].gy*span))
    return RiverRoute[SurfaceGridCoord](river_uid=uid, segments=(RiverPathSegment[SurfaceGridCoord](
        path=path, connection_type=kind, edge_uid=uid+"-edge", location_uid=None, declared=declared),),
        receiver_cell=path[-1], drainage=link)


def coarse(*routes):
    claims = {cell: MapCellHydrology(role=HydrologyCellRole.RIVER_BED, water_body_uid=r.river_uid,
        connection_edge_uid=s.edge_uid, river_drainage=r.drainage)
        for r in routes for s in r.segments for cell in s.path if cell != r.receiver_cell}
    return CoarseRiverPlan(routes=routes, claims=tuple(sorted(claims.items(), key=lambda row: (row[0].gy, row[0].gx))))


class ProceduralRefinementTests(TestCase):
    def test_real_coarse_autoresolve_refines_same_uids_without_rediscovery(self):
        physical, water = native(self)
        window, assembled = water.payload
        surface = dict(window.surface_z)
        heights = tuple((SurfaceGridCoord(x, y), surface[x*16+8, y*16+8]) for y in range(2) for x in range(2))
        projection = OpenWaterPlan(coarse_open_water=((SurfaceGridCoord(1, 0), dict(assembled.materialized.cells)[24, 8]),),
            water_bodies=assembled.materialized.bodies, physical_unions=assembled.physical_unions,
            source_mapping=assembled.materialized.source_mapping)
        accepted = CoarseRiverPlanner().plan(world_uid="world", inputs=physical, surface_z=heights,
            water=projection, control=Control()).payload
        self.assertTrue(accepted.routes)
        before = encode(water, SURFACE_MANIFEST)
        with patch("app.application.worldData.generators.hydrology.rivers.riverNetworkPlanner.plan_prepared_river_network",
                   side_effect=AssertionError("source rediscovery")):
            result = route(physical, water, coarse=accepted)
        self.assertEqual({r.river_uid for r in result.payload.routes}, {r.river_uid for r in accepted.routes})
        self.assertTrue(all(r.drainage.receiver_uid == "lake" for r in result.payload.routes))
        self.assertEqual({s.edge_uid for r in result.payload.routes for s in r.segments},
                         {s.edge_uid for r in accepted.routes for s in r.segments})
        self.assertFalse(any(d.disposition is PlanDiagnosticDisposition.ERROR for d in result.diagnostics))
        self.assertLess(len(result.payload.base_surface_z), len(window.surface_z))
        self.assertEqual(encode(water, SURFACE_MANIFEST), before)
        self.assertEqual(decode(encode(result, SURFACE_MANIFEST), PlanEnvelope[FineRiverPlan], SURFACE_MANIFEST), result)

    def test_parent_refines_before_child_and_claims_are_fine_proven(self):
        physical, water = native(self)
        parent = proposal("parent", ((0, 0), (1, 0)))
        child = proposal("child", ((0, 1), (0, 0)), "parent")
        result = route(physical, water, coarse=coarse(child, parent))
        self.assertEqual([r.river_uid for r in result.payload.routes], ["parent", "child"])
        self.assertEqual(result.payload.routes[0].drainage.receiver_uid, "lake")
        self.assertEqual(result.payload.routes[1].drainage.receiver_uid, "parent")
        self.assertEqual(result.payload.routes[1].receiver_cell, (8, 8))
        self.assertFalse(any(d.disposition is PlanDiagnosticDisposition.ERROR for d in result.diagnostics))

    def test_rejected_parent_cannot_be_supplied_by_coarse_claims(self):
        physical, water = native(self, parent_wet=True)
        physical = replace(physical, resolution_mode=ResolutionMode.VALIDATE_ONLY)
        accepted = coarse(proposal("child", ((0, 1), (0, 0)), "parent"), proposal("parent", ((0, 0), (1, 0))))
        result = route(physical, water, coarse=accepted)
        self.assertEqual(result.payload.routes, ())
        errors = {fact.object_uid: fact for d in result.diagnostics if d.disposition is PlanDiagnosticDisposition.ERROR
                  for fact in (RiverRouteDiagnostic.model_validate_json(d.issue.message),)}
        self.assertEqual(set(errors), {"parent", "child"})
        self.assertIs(errors["parent"].reason, RiverRoutingFailure.SOURCE_IN_WATER)
        self.assertIs(errors["child"].reason, RiverRoutingFailure.WRONG_BODY)

    def test_coarse_wet_membership_is_not_a_receiver_and_has_explicit_rejection(self):
        physical, water = native(self, wet=False)
        physical = replace(physical, resolution_mode=ResolutionMode.VALIDATE_ONLY)
        result = route(physical, water, coarse=coarse(proposal("no-prefix", ((0, 0), (1, 0)))))
        self.assertEqual(result.payload.routes, ())
        errors = [RiverRouteDiagnostic.model_validate_json(d.issue.message) for d in result.diagnostics
                  if d.disposition is PlanDiagnosticDisposition.ERROR]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].object_uid, "no-prefix")
        self.assertIs(errors[0].code, RiverRoutingCode.NO_WATER_BODIES)
        self.assertIs(errors[0].reason, RiverRoutingFailure.DRY_MOUTH)

    def test_fine_classification_and_proposal_identity_are_not_coarse_proofs(self):
        physical, water = native(self)
        accepted = coarse(proposal("plain-identity", ((0, 0), (1, 0)), kind=Kind.MOUNTAIN_RIVER))
        result = route(physical, water, coarse=accepted)
        self.assertEqual(len(result.payload.routes), 1)
        self.assertEqual(result.payload.routes[0].river_uid, "plain-identity")
        self.assertIs(result.payload.routes[0].segments[0].connection_type, Kind.RIVER)
        renamed = coarse(proposal("different", ((0, 0), (1, 0)), kind=Kind.MOUNTAIN_RIVER))
        self.assertNotEqual(result.ref.key, route(physical, water, coarse=renamed).ref.key)
        with self.assertRaises(PlanBuildFailure):
            route(replace(physical, enabled=False), water, coarse=accepted)
        with self.assertRaises(PlanBuildFailure):
            route(physical, water, coarse=coarse(proposal("outside", ((-1, 0), (1, 0)))))

    def test_declared_membership_and_historical_results_do_not_depend_on_segment_flag(self):
        expected = ("1ccb025f9dbc28083d7751293bec109823d7970836ce4eee6c882aef07c8eeb2",
            "36204c395f88de16bcce6fd87990059e7554bd1402c26c8879560e4b9beee067",
            "a5fcf7d389a726efbcfa4eeaca352a9bc9030f7a64826abf6775ee0d22fa4da6")
        for settings, fingerprint in zip(({}, {"lake": False}, {"mouth": (8, 11)}), expected, strict=True):
            _, physical, water = scenario(**settings)
            result = route(physical, water)
            self.assertEqual(digest((result.payload, result.diagnostics), SURFACE_MANIFEST).hex(), fingerprint)
            again = route(physical, water, coarse=coarse(proposal("river", ((0, 0), (1, 0)), declared=False)))
            self.assertEqual(again.payload, result.payload)
            self.assertEqual(again.diagnostics, result.diagnostics)

    def test_projection_handles_negative_coordinates_and_wrapped_seams(self):
        topology = WorldTopology(mode=WorldTopologyMode.WRAPPED,
            bounds=WorldBounds(x_min=-16, x_max=31, y_min=0, y_max=15))
        request = procedural_requests((proposal("seam", ((1, 0), (-1, 0))),), span=16,
            heightmap=SurfaceHeightmap("world", GridBBox(-16, 31, 0, 15), {}), occupied={},
            topology=topology, control=Control())[0]
        self.assertEqual(request.source, (24, 8))
        self.assertEqual(request.target, (-8, 8))
        self.assertEqual(request.segments[0].polyline_cells,
                         [(x, 8) for x in range(24, 32)]+[(x, 8) for x in range(-16, -7)])
        for span in (1, 3, 16):
            with self.subTest(sphere_span=span):
                bounds = WorldBounds(x_min=0, x_max=4*span-1, y_min=0, y_max=2*span-1)
                sphere = WorldTopology(mode=WorldTopologyMode.SPHERE, bounds=bounds)
                request = procedural_requests((proposal("pole", ((0, 0), (2, 0)), span=span),), span=span,
                    heightmap=SurfaceHeightmap("world", GridBBox(0, 4*span-1, 0, 2*span-1), {}), occupied={},
                    topology=sphere, control=Control())[0]
                path = request.segments[0].polyline_cells
                self.assertEqual(request.source, (span//2, span//2))
                self.assertEqual(request.target, (2*span+span//2, span//2))
                self.assertEqual(len(path), 2*(span//2)+2)
                self.assertTrue(all(b in canonical_neighbors8(sphere, a) for a, b in zip(path, path[1:])))

    def test_system_container_without_geometry_does_not_hide_a_proposal(self):
        physical, water = native(self)
        system = DeclaredRiver.model_validate(dict(location_uid="system", system_role="system",
                                                   river_system_topology="basin"))
        result = route(replace(physical, declared_rivers=(system,)), water,
                       coarse=coarse(proposal("system", ((0, 0), (1, 0)))))
        self.assertEqual([r.river_uid for r in result.payload.routes], ["system"])
