from copy import replace
from unittest import TestCase
from unittest.mock import patch

from app.application.encoding.canonicalCodec import encode, decode
from app.application.planning.service.planFingerprints import output_fingerprint
from app.application.planning.service.planningService import PlanBuildFailure
from app.application.policy.policyResolver import PolicyResolver
from app.application.worldData.generators.hydrology.planning.assembly.hydrologyRoutesAssembler import HydrologyRoutesAssembler
from app.application.worldData.generators.hydrology.water.planning.waterBodyPlanner import WaterBodyPlanner
from app.application.worldData.generators.hydrology.water.planning.fine.publication import FineWaterPublicationJob
from app.application.worldData.generators.hydrology.rivers.planning.coarseRiverPlanner import CoarseRiverPlanner
from app.application.worldData.generators.hydrology.rivers.planning.fineRiverPlanner import FineRiverPlanner
from app.application.worldData.generators.hydrology.load.paint.declaredWaterPaintProjector import DeclaredWaterPaintProjector
from app.application.worldData.generators.terrain.planning.projection.coarseSurface import TerrainProjectionPlanner
from app.application.worldData.generators.terrain.planning.preWater.terrainBaseJob import PreWaterTerrainJob
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.declaredRiver import DeclaredRiver
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyRoutesPlan
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from tests.geo1.hill_hosts.test_hosts import coverage
from tests.geo1.fine_water.fixtures import decisions, physical_inputs
from tests.geo1.fine_water.test_fill import source, fill, basin
from tests.geo1.procedural_refinement.test_proposals import native
from tests.geo1.terrain_base.fixtures import Control


def owner():
    return HydrologyRoutesAssembler(WaterBodyPlanner(), CoarseRiverPlanner(),
                                    FineRiverPlanner(), DeclaredWaterPaintProjector())


def project(inputs, water, specs, terminal):
    return WaterBodyPlanner().project_fine(water, expected_water=water.ref, world_uid="world",
        inputs=inputs, specs=specs, classification_decisions=terminal, control=Control())


def assemble(inputs, water, specs, terminal):
    return owner().assemble_fine(world_uid="world", inputs=inputs, water=water, expected_water=water.ref,
        specs=specs, classification_decisions=terminal, control=Control())


def resign(water, **changes):
    water = replace(water, **changes)
    return replace(water, ref=replace(water.ref, output_fingerprint=output_fingerprint(
        water.payload, water.dependencies, water.diagnostics, SURFACE_MANIFEST)))


class SourceProjectionTests(TestCase):
    def test_real_native_stage_has_one_source_admission_and_no_refill_or_policy_resolution(self):
        inputs, water = native(self)
        specs = (basin("lake", {(24, 8), (25, 8), (24, 9), (25, 9)}),)
        terminal = decisions(inputs)
        before = encode(water, SURFACE_MANIFEST)
        with patch.object(PreWaterTerrainJob, "__init__", side_effect=AssertionError("terrain replay")), \
             patch.object(WaterBodyPlanner, "plan_geo", side_effect=AssertionError("coarse fill")), \
             patch.object(FineWaterPublicationJob, "publish", side_effect=AssertionError("fine refill")), \
             patch.object(PolicyResolver, "resolve", side_effect=AssertionError("policy re-resolution")), \
             patch.object(FineWaterPublicationJob, "admit_result", wraps=FineWaterPublicationJob.admit_result) as admit:
            result = assemble(inputs, water, specs, terminal)
        self.assertEqual(admit.call_count, 1)
        self.assertTrue(result.payload.base.coarse_routes)
        self.assertEqual({r.river_uid for r in result.payload.base.fine_routes},
                         {r.river_uid for r in result.payload.base.coarse_routes})
        self.assertEqual(result.dependencies[0].slot, "fine_water")
        self.assertEqual(result.dependencies[0].ref, water.ref)
        self.assertEqual(result.payload.source_mapping, water.payload[1].materialized.source_mapping)
        self.assertEqual(result.payload.classification_decisions, terminal)
        self.assertLess(len(result.payload.base.fine_base_surface_z), len(water.payload[0].surface_z))
        self.assertEqual(encode(water, SURFACE_MANIFEST), before)
        self.assertEqual(decode(encode(result, SURFACE_MANIFEST), PlanEnvelope[GeoHydrologyRoutesPlan], SURFACE_MANIFEST), result)
        surface = TerrainProjectionPlanner().project_coarse(water.payload[0], topology=inputs.topology,
            grid=inputs.grid, control=Control())
        self.assertEqual(next(z for c, z in surface.surface_z if (c.gx, c.gy) == (1, 0)), -5)

    def test_body_missed_by_coarse_sample_still_receives_native_fine_river(self):
        window, _, topology = source(hills=False)
        river = DeclaredRiver.model_validate(dict(location_uid="river", declare_mode="segments",
            segments=[{"from": dict(x=2, y=11), "to": dict(x=11, y=11), "connection_type": "river"}]))
        inputs = replace(physical_inputs(topology), enabled=True, declared_rivers=(river,))
        specs = (basin("lake", {(x, y) for y in range(10, 14) for x in range(10, 14)}),)
        water = fill(window, topology, specs, physical=inputs)
        terminal = decisions(inputs)
        projected = project(inputs, water, specs, terminal).payload
        self.assertEqual(projected.coarse_open_water, ())
        self.assertEqual([b.water_body_uid for b in projected.water_bodies], ["lake"])
        result = assemble(inputs, water, specs, terminal)
        self.assertEqual([r.river_uid for r in result.payload.base.fine_routes], ["river"])
        self.assertEqual(result.payload.base.fine_routes[0].drainage.receiver_uid, "lake")
        # Coarse proposals can fail; that is not an all-intent fine success proof.
        self.assertTrue(result.diagnostics)

    def test_exact_sample_preserves_dry_shore_and_unsampled_body_metadata(self):
        window, _, topology = source(hills=False)
        inputs = physical_inputs(topology)
        specs = (basin("near", {(9, 8), (10, 8), (9, 9), (10, 9)}),
                 basin("far", {(24, 24), (25, 24), (24, 25), (25, 25)}))
        water = fill(window, topology, specs, physical=inputs)
        fine = dict(water.payload[1].materialized.cells)
        self.assertIs(fine[8, 8].role, HydrologyCellRole.SHORE)
        result = project(inputs, water, specs, decisions(inputs)).payload
        sample = next(value for cell, value in result.coarse_open_water if (cell.gx, cell.gy) == (0, 0))
        self.assertEqual(sample, fine[8, 8])
        self.assertFalse(sample.liquid_candidate)
        self.assertEqual(result.water_bodies, water.payload[1].materialized.bodies)
        self.assertEqual(result.physical_unions, water.payload[1].physical_unions)
        self.assertEqual(result.source_mapping, water.payload[1].materialized.source_mapping)

    def test_terminal_decisions_specs_and_physical_capture_must_match_source_key(self):
        inputs, water = native(self)
        specs = (basin("lake", {(24, 8), (25, 8), (24, 9), (25, 9)}),)
        terminal = decisions(inputs)
        variants = ((replace(inputs, change_uid="other"), specs, terminal),
                    (inputs, (), terminal), (inputs, specs, decisions(inputs, auto=True)))
        for physical, basins, categories in variants:
            with self.subTest(physical=physical.change_uid, specs=bool(basins)), self.assertRaisesRegex(ValueError, "inputs/specs/decisions"):
                assemble(physical, water, basins, categories)

    def test_partial_coverage_is_unknown_not_dry_or_zero(self):
        inputs, water = native(self)
        window, assembled = water.payload
        q = coverage(0, 1, 0, 1)
        partial = FineSurfaceWindow(coverage=q, surface_z=(((0, 0), dict(window.surface_z)[0, 0]),),
            topology=window.topology, protected_cells=frozenset())
        # Sparse observation with empty water is not proof for any other cell.
        empty = replace(assembled, materialized=replace(assembled.materialized, cells=()))
        candidate = resign(water, payload=(partial, empty))
        specs = (basin("lake", {(24, 8), (25, 8), (24, 9), (25, 9)}),)
        with self.assertRaises(PlanBuildFailure):
            project(inputs, candidate, specs, decisions(inputs))
        with self.assertRaises(PlanBuildFailure):
            TerrainProjectionPlanner().project_coarse(partial, topology=inputs.topology,
                grid=inputs.grid, control=Control())

    def test_source_error_tamper_stale_and_foreign_world_fail_before_projection(self):
        inputs, water = native(self)
        specs = (basin("lake", {(24, 8), (25, 8), (24, 9), (25, 9)}),)
        terminal = decisions(inputs)
        error = PlanDiagnostic(issue=FieldPathError(("source",), "failed"), disposition=PlanDiagnosticDisposition.ERROR)
        failed = resign(water, diagnostics=(error,))
        foreign = replace(water, ref=replace(water.ref, key=replace(water.ref.key, world_uid="other")))
        tampered = replace(water, payload=(water.payload[0], replace(water.payload[1], physical_unions=())))
        # Tamper height data even when this fixture has no union records.
        changed = replace(water.payload[0], surface_z=tuple((c, z+1) for c, z in water.payload[0].surface_z))
        tampered = replace(tampered, payload=(changed, tampered.payload[1]))
        with patch.object(TerrainProjectionPlanner, "project_coarse", side_effect=AssertionError("before admission")):
            with self.assertRaises(PlanBuildFailure):
                assemble(inputs, failed, specs, terminal)
            for candidate in (foreign, tampered):
                with self.subTest(candidate=candidate.ref), self.assertRaises(ValueError):
                    assemble(inputs, candidate, specs, terminal)
            with self.assertRaisesRegex(ValueError, "revision"):
                owner().assemble_fine(world_uid="world", inputs=inputs, water=water, expected_water=foreign.ref,
                    specs=specs, classification_decisions=terminal, control=Control())

    def test_height_centers_for_negative_odd_and_seam_frames_without_full_iteration(self):
        class IndexedRows(tuple):
            def __iter__(self):
                raise AssertionError("projection scanned/copied complete fine rows")
        for mode in WorldTopologyMode:
            for span in (1, 3, 16):
                with self.subTest(mode=mode, span=span):
                    topology = WorldTopology(mode=mode, bounds=WorldBounds(x_min=-1, x_max=0, y_min=-1, y_max=0))
                    grid = SurfaceGridSettings(fine_span=span, light_side=1)
                    observed = coverage(-span, span, -span, span)
                    rows = tuple(((x, s.y), x*100+s.y) for s in observed.spans for x in range(s.x0, s.x1))
                    window = FineSurfaceWindow(coverage=observed, surface_z=rows, protected_cells=frozenset(),
                        topology=fine_topology(topology, span))
                    object.__setattr__(window, "surface_z", IndexedRows(window.surface_z))
                    result = TerrainProjectionPlanner().project_coarse(window, topology=topology, grid=grid, control=Control())
                    self.assertEqual({(c.gx, c.gy): z for c, z in result.surface_z},
                        {(x, y): (x*span+span//2)*100+y*span+span//2 for y in (-1, 0) for x in (-1, 0)})

    def test_native_identity_tracks_source_operation_even_for_equal_geometry_and_cancels(self):
        window, _, topology = source(hills=False)
        inputs = physical_inputs(topology)
        specs = (basin("lake", {(24, 8), (25, 8), (24, 9), (25, 9)}),)
        terminal = decisions(inputs)
        first = fill(window, topology, specs, physical=inputs)
        changed = replace(inputs, change_uid="new-operation")
        second = fill(window, topology, specs, physical=changed)
        self.assertEqual(first.payload, second.payload)
        a, b = assemble(inputs, first, specs, terminal), assemble(changed, second, specs, terminal)
        self.assertEqual(a.payload, b.payload)
        self.assertNotEqual(a.ref.key, b.ref.key)
        self.assertNotEqual(a.ref.output_fingerprint, b.ref.output_fingerprint)
        class Stop:
            def raise_if_shutdown(self):
                raise InterruptedError("cancelled")
        with self.assertRaises(InterruptedError):
            owner().assemble_fine(world_uid="world", inputs=inputs, water=first, expected_water=first.ref,
                specs=specs, classification_decisions=terminal, control=Stop())
