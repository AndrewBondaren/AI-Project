from copy import replace
from unittest import TestCase
from unittest.mock import patch

from app.application.encoding.canonicalCodec import encode, decode
from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.relief.planning.riverReliefPlanner import RiverReliefPlanner
from app.application.worldData.generators.terrain.relief.planning.river.execution import NativeRiverReliefJob
from app.application.worldData.generators.terrain.reliefObjects.riverBed.riverBedZ import river_bed_spec, apply_river_bed_z
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.application.worldData.generators.hydrology.types import RiverSegment
from app.application.worldData.generators.hydrology.water.planning.fine.publication import FineWaterPublicationJob
from app.application.worldData.generators.terrain.planning.projection.coarseSurface import TerrainProjectionPlanner
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.declaredRiver import DeclaredRiver
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType as Kind
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.planning.hydrologyPlan import RiverRoute, RiverPathSegment
from app.dataModel.hydrology.riverDrainageLink import RiverDrainageLink
from app.dataModel.spatial.grid.coordinateTypes import FineXY
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import RiverReliefInput
from app.dataModel.terrain.relief.planning.reliefPlan import RiverReliefPlan
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from tests.geo1.source_projection.test_projection import assemble, resign
from tests.geo1.procedural_refinement.test_proposals import native
from tests.geo1.fine_water.test_fill import source, fill, basin
from tests.geo1.fine_water.fixtures import physical_inputs, decisions
from tests.geo1.terrain_base.fixtures import Control


def relief_input(inputs, depth=2):
    return RiverReliefInput(z_min=inputs.z_min, z_max=inputs.z_max, grid=inputs.grid,
        topology=inputs.topology, channel_depths=((Kind.MOUNTAIN_RIVER, depth+1), (Kind.RIVER, depth)))


def run(inputs, water, routes, *, settings=None, control=None):
    return RiverReliefPlanner().plan_fine(settings or relief_input(inputs), world_uid="world",
        routing_inputs=inputs, water=water, expected_water=water.ref,
        routes=routes, expected_routes=routes.ref, control=control or Control())


def setup_native(case):
    inputs, water = native(case)
    specs = (basin("lake", {(24, 8), (25, 8), (24, 9), (25, 9)}),)
    return inputs, water, assemble(inputs, water, specs, decisions(inputs))


class NativeReliefTests(TestCase):
    def test_actual_stage_matches_full_kernel_reference_and_retains_only_H(self):
        inputs, water, routes = setup_native(self)
        before = encode((water, routes), SURFACE_MANIFEST)
        with patch("app.application.worldData.generators.terrain.relief.planning.river.beds.SurfaceHeightmap",
                   wraps=SurfaceHeightmap) as snapshot, \
             patch.object(FineWaterPublicationJob, "publish", side_effect=AssertionError("refill")):
            result = run(inputs, water, routes)
        self.assertEqual(len(snapshot.call_args.kwargs["surface_z"]), len(routes.payload.base.fine_base_surface_z))
        self.assertLess(len(result.payload.fine_surface_z), len(water.payload[0].surface_z))
        window = water.payload[0]
        b = window.topology.bounds
        full = SurfaceHeightmap(world_uid="world", bbox=GridBBox(b.x_min, b.x_max, b.y_min, b.y_max),
                                surface_z=dict(window.surface_z))
        specs = []
        for route in routes.payload.base.fine_routes:
            for segment in route.segments:
                specs.append(river_bed_spec(full, RiverSegment(list(segment.path), segment.connection_type.value),
                    depth_step=dict(relief_input(inputs).channel_depths)[segment.connection_type],
                    z_min=inputs.z_min, occupied={}, receiver_cell=route.receiver_cell))
        apply_river_bed_z(full, specs)
        self.assertTrue(specs)
        self.assertEqual(dict(result.payload.fine_surface_z),
                         {cell: full.surface_z[cell] for cell, _ in routes.payload.base.fine_base_surface_z})
        span = inputs.grid.fine_span
        self.assertEqual(dict(result.payload.surface_z), {c: full.surface_z[c.gx*span+span//2, c.gy*span+span//2]
                                                        for c, _ in result.payload.surface_z})
        for bed in result.payload.fine_beds:
            self.assertEqual(dict(bed.bed_z), {cell: full.surface_z[cell] for cell, _ in bed.bed_z})
        self.assertEqual(result.payload.coarse_beds, ())
        self.assertEqual({d.slot: d.ref for d in result.dependencies},
                         {"fine_water": water.ref, "hydrology_routes": routes.ref})
        self.assertEqual(encode((water, routes), SURFACE_MANIFEST), before)
        self.assertEqual(decode(encode(result, SURFACE_MANIFEST), PlanEnvelope[RiverReliefPlan], SURFACE_MANIFEST), result)

    def test_unsampled_lake_receiver_is_preserved_and_route_errors_are_not_completeness(self):
        window, _, topology = source(hills=False)
        river = DeclaredRiver.model_validate(dict(location_uid="river", declare_mode="segments",
            segments=[{"from": dict(x=2, y=11), "to": dict(x=11, y=11), "connection_type": "river"}]))
        inputs = replace(physical_inputs(topology), enabled=True, declared_rivers=(river,))
        specs = (basin("lake", {(x, y) for y in range(10, 14) for x in range(10, 14)}),)
        water = fill(window, topology, specs, physical=inputs)
        routes = assemble(inputs, water, specs, decisions(inputs))
        self.assertFalse(routes.payload.base.coarse_open_water)
        self.assertTrue(routes.diagnostics)
        result = run(inputs, water, routes)
        self.assertEqual(result.diagnostics, routes.diagnostics)
        route = routes.payload.base.fine_routes[0]
        self.assertEqual(route.drainage.receiver_uid, "lake")
        self.assertNotIn(route.receiver_cell, dict(result.payload.fine_beds[0].bed_z))
        self.assertEqual(dict(result.payload.fine_surface_z)[route.receiver_cell],
                         dict(water.payload[0].surface_z)[route.receiver_cell])

    def test_coarse_is_actual_fine_projection_even_when_coarse_proposal_has_a_bed(self):
        window, _, topology = source(hills=False)
        river = DeclaredRiver.model_validate(dict(location_uid="offset-river", declare_mode="segments",
            segments=[{"from": dict(x=2, y=11), "to": dict(x=24, y=11), "connection_type": "river"}]))
        inputs = replace(physical_inputs(topology), enabled=True, declared_rivers=(river,))
        specs = (basin("lake", {(x, y) for y in range(8, 14) for x in range(24, 28)}),)
        water = fill(window, topology, specs, physical=inputs)
        routes = assemble(inputs, water, specs, decisions(inputs))
        self.assertTrue(routes.payload.base.coarse_routes)
        self.assertTrue(routes.payload.base.fine_routes)
        result = run(inputs, water, routes)
        pre = TerrainProjectionPlanner().project_coarse(water.payload[0], topology=inputs.topology,
                                                       grid=inputs.grid, control=Control())
        fine = dict(result.payload.fine_surface_z)
        span = inputs.grid.fine_span
        differs = False
        for route in routes.payload.base.coarse_routes:
            for segment in route.segments:
                for cell in segment.path:
                    if cell == route.receiver_cell:
                        continue
                    sample = (cell.gx*span+span//2, cell.gy*span+span//2)
                    expected = fine.get(sample, dict(water.payload[0].surface_z)[sample])
                    self.assertEqual(dict(result.payload.surface_z)[cell], expected)
                    independently_carved = max(inputs.z_min, dict(pre.surface_z)[cell]-2)
                    differs |= expected != independently_carved
        self.assertTrue(differs, "fixture must expose the independent coarse-carve disagreement")

    def test_stale_tampered_cross_source_input_and_frame_fail_before_execution(self):
        inputs, water, routes = setup_native(self)
        settings = relief_input(inputs)
        foreign = replace(water, ref=replace(water.ref, key=replace(water.ref.key, world_uid="other")))
        with patch.object(NativeRiverReliefJob, "plan", side_effect=AssertionError("before admission")):
            stale = replace(water, ref=replace(water.ref, key=replace(water.ref.key,
                algorithm_version=water.ref.key.algorithm_version+1)))
            for candidate in (foreign, stale):
                with self.subTest(ref=candidate.ref), self.assertRaises(ValueError):
                    run(inputs, candidate, routes)
            with self.assertRaises(ValueError):
                run(replace(inputs, change_uid="another"), water, routes)
            with self.assertRaises(ValueError):
                run(inputs, water, routes, settings=replace(settings, z_min=settings.z_min-1))
            with self.assertRaises(ValueError):
                RiverReliefPlanner().plan_fine(settings, world_uid="world", routing_inputs=inputs,
                    water=water, expected_water=water.ref, routes=routes, expected_routes=water.ref, control=Control())
            changed = replace(routes, payload=replace(routes.payload, classification_decisions=()))
            with self.assertRaises(ValueError):
                run(inputs, water, changed)

    def test_re_signed_inconsistent_retained_height_is_rejected_not_carved(self):
        inputs, water, routes = setup_native(self)
        base = routes.payload.base
        cell, z = base.fine_base_surface_z[0]
        invalid = replace(base, fine_base_surface_z=((cell, z+1), *base.fine_base_surface_z[1:]))
        changed = resign(routes, payload=replace(routes.payload, base=invalid))
        with self.assertRaises(PlanBuildFailure) as error:
            run(inputs, water, changed)
        self.assertIn("canonical fine water", str(error.exception.issues))

    def test_source_errors_block_but_route_issues_are_preserved(self):
        inputs, water, routes = setup_native(self)
        issue = PlanDiagnostic(issue=FieldPathError(("water",), "failed"), disposition=PlanDiagnosticDisposition.ERROR)
        failed = resign(water, diagnostics=(*water.diagnostics, issue))
        # Bind the failing source explicitly; water admission must still block it.
        from app.application.worldData.generators.hydrology.planning.assembly.nativeRoutesPublication import NativeRoutesPublicationJob
        from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
        bound = NativeRoutesPublicationJob().publish(PlanBuildResult(payload=routes.payload, diagnostics=()),
            world_uid="world", inputs=inputs, water=failed.ref, control=Control())
        with self.assertRaises(PlanBuildFailure):
            run(inputs, failed, bound)
        route_issue = resign(routes, diagnostics=(*routes.diagnostics, issue))
        self.assertIn(issue, run(inputs, water, route_issue).diagnostics)

    def test_sparse_overlay_uses_indexed_source_and_rejects_unobserved_rows(self):
        inputs, water, _ = setup_native(self)
        class IndexedRows(tuple):
            def __iter__(self):
                raise AssertionError("projection copied/scanned full fine source")
        surface = replace(water.payload[0])
        object.__setattr__(surface, "surface_z", IndexedRows(surface.surface_z))
        projected = TerrainProjectionPlanner().project_coarse(surface, topology=inputs.topology,
            grid=inputs.grid, overlay=(((8, 8), -17),), control=Control())
        self.assertEqual(next(z for c, z in projected.surface_z if (c.gx, c.gy) == (0, 0)), -17)
        with self.assertRaises(PlanBuildFailure):
            TerrainProjectionPlanner().project_coarse(surface, topology=inputs.topology,
                grid=inputs.grid, overlay=(((100, 100), 1),), control=Control())

    def test_depth_revision_and_cancellation(self):
        inputs, water, routes = setup_native(self)
        first = run(inputs, water, routes)
        second = run(inputs, water, routes, settings=relief_input(inputs, depth=3))
        self.assertNotEqual(first.ref.key, second.ref.key)
        self.assertNotEqual(first.payload.fine_beds, second.payload.fine_beds)
        class Stop:
            def raise_if_shutdown(self):
                raise InterruptedError("cancelled")
        with self.assertRaises(InterruptedError):
            run(inputs, water, routes, control=Stop())

    def test_shared_beds_use_pre_bed_minimum_and_parent_alone_writes_tributary_receiver(self):
        inputs, water, routes = setup_native(self)
        parent_path = ((8, 6), (8, 7), *((x, 8) for x in range(8, 25)))
        child_path = ((8, 6), (8, 7), (8, 8))
        def route(uid, path, kind, receiver, receiver_kind):
            return RiverRoute[FineXY](river_uid=uid, segments=(RiverPathSegment[FineXY](
                path=path, connection_type=kind, edge_uid=uid+"-edge", location_uid=None, declared=True),),
                receiver_cell=path[-1], drainage=RiverDrainageLink(river_uid=uid, river_type=kind,
                    receiver_uid=receiver, receiver_kind=receiver_kind, receiver_cell=path[-1]))
        parent = route("parent", parent_path, Kind.RIVER, "lake", BasinKind.LAKE)
        child = route("child", child_path, Kind.MOUNTAIN_RIVER, "parent", Kind.RIVER)
        heights = dict(water.payload[0].surface_z)
        samples = tuple((cell, heights[cell]) for cell in sorted(set(parent_path+child_path), key=lambda c: (c[1], c[0])))
        base = replace(routes.payload.base, fine_routes=(parent, child), fine_base_surface_z=samples)
        result = NativeRiverReliefJob().plan(relief_input(inputs), world_uid="world", water=water.payload,
                                             routes=replace(routes.payload, base=base), control=Control())
        beds = {bed.river_uid: dict(bed.bed_z) for bed in result.fine_beds}
        self.assertEqual(beds["parent"][8, 6], heights[8, 6]-3)
        self.assertEqual(beds["child"][8, 6], heights[8, 6]-3)
        self.assertNotIn((8, 8), beds["child"])
        self.assertEqual(beds["parent"][8, 8], heights[8, 8]-2)
        self.assertEqual(dict(result.fine_surface_z)[24, 8], heights[24, 8])
        reversed_result = NativeRiverReliefJob().plan(relief_input(inputs), world_uid="world", water=water.payload,
            routes=replace(routes.payload, base=replace(base, fine_routes=(child, parent))), control=Control())
        self.assertEqual(result.fine_surface_z, reversed_result.fine_surface_z)
