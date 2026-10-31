"""Source-to-route contracts using real pre-water terrain, placement and fill."""
from copy import replace
from unittest import TestCase

from app.application.encoding.canonicalCodec import encode, decode
from app.application.planning.service.planFingerprints import output_fingerprint
from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.hydrology.rivers.planning.fineRiverPlanner import FineRiverPlanner
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.declaredRiver import DeclaredRiver
from app.dataModel.hydrology.planning.stages.riverRoutePlans import FineRiverPlan
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.immutableValue import validate_immutable
from tests.geo1.fine_water.fixtures import physical_inputs
from tests.geo1.fine_water.test_fill import source, fill, basin
from tests.geo1.terrain_base.fixtures import Control


def scenario(*, mouth=(11, 11), lake=True):
    window, _, topology = source(hills=False)
    declared = DeclaredRiver.model_validate(dict(location_uid="river", declare_mode="segments",
        segments=[{"from": dict(x=2, y=11), "to": dict(x=mouth[0], y=mouth[1]), "connection_type": "river"}]))
    inputs = replace(physical_inputs(topology), enabled=True, declared_rivers=(declared,))
    specs = (basin("lake", {(x, y) for y in range(10, 14) for x in range(10, 14)}),) if lake else ()
    return window, inputs, fill(window, topology, specs, physical=inputs)


def route(inputs, water, *, expected=None, world="world", control=None):
    return FineRiverPlanner().plan_fine(world_uid=world, inputs=inputs, water=water,
        expected_water=expected or water.ref, control=control or Control())


class FineRoutingTests(TestCase):
    def test_narrow_lake_uses_actual_fine_heights_receiver_and_sparse_retention(self):
        window, inputs, water = scenario()
        before = encode(water, SURFACE_MANIFEST)
        result = route(inputs, water)
        self.assertEqual(len(result.payload.routes), 1)
        accepted = result.payload.routes[0]
        self.assertEqual(accepted.drainage.receiver_uid, "lake")
        self.assertEqual(accepted.receiver_cell, (10, 11))
        samples = dict(result.payload.base_surface_z)
        actual = dict(water.payload[0].surface_z)
        self.assertEqual(samples[accepted.receiver_cell], -5)
        self.assertGreaterEqual(dict(window.payload.surface_z)[accepted.receiver_cell], 0)
        self.assertEqual(samples, {cell: actual[cell] for cell in samples})
        self.assertGreater(len(set(samples.values())), 2)
        self.assertLess(len(samples), len(actual) // 10)
        self.assertEqual(tuple(dep.ref for dep in result.dependencies), (water.ref,))
        self.assertEqual(result.dependencies[0].slot, "fine_water")
        self.assertEqual(encode(water, SURFACE_MANIFEST), before)
        validate_immutable(result)
        self.assertEqual(decode(encode(result, SURFACE_MANIFEST), PlanEnvelope[FineRiverPlan], SURFACE_MANIFEST), result)
        self.assertEqual(route(inputs, water), result)

    def test_dry_fine_mouth_is_not_made_wet_by_coarse_cell_membership(self):
        # (14,11) and lake share coarse (0,0), but the endpoint itself is dry.
        _, inputs, water = scenario(mouth=(14, 11))
        endpoint = dict(water.payload[1].materialized.cells).get((14, 11))
        self.assertTrue(endpoint is None or not endpoint.liquid_candidate)
        result = route(inputs, water)
        for accepted in result.payload.routes:
            entry = dict(water.payload[1].materialized.cells)[accepted.receiver_cell]
            self.assertTrue(entry.liquid_candidate)
            self.assertEqual(entry.water_body_uid, accepted.drainage.receiver_uid)
            self.assertNotEqual(accepted.receiver_cell, (14, 11))
        self.assertTrue(result.payload.routes or result.diagnostics)

    def test_no_receiving_water_cannot_publish_a_successful_river(self):
        _, inputs, water = scenario(lake=False)
        result = route(inputs, water)
        self.assertEqual(result.payload.routes, ())
        self.assertTrue(result.diagnostics)

    def test_exact_source_proof_world_topology_and_error_are_required(self):
        _, inputs, water = scenario()
        _, _, empty = scenario(lake=False)
        with self.assertRaisesRegex(ValueError, "revision"):
            route(inputs, water, expected=empty.ref)
        with self.assertRaisesRegex(ValueError, "revision"):
            route(inputs, water, world="other")
        bad = replace(water, payload=(water.payload[0], empty.payload[1]))
        with self.assertRaisesRegex(ValueError, "proof"):
            route(inputs, bad)
        with self.assertRaisesRegex(ValueError, "topology"):
            route(replace(inputs, grid=replace(inputs.grid, fine_span=32)), water)
        diagnostics = (PlanDiagnostic(issue=FieldPathError(("water",), "failed resolution"),
                                      disposition=PlanDiagnosticDisposition.ERROR),)
        failed = replace(water, diagnostics=diagnostics,
            ref=replace(water.ref, output_fingerprint=output_fingerprint(
                water.payload, water.dependencies, diagnostics, SURFACE_MANIFEST)))
        with self.assertRaises(PlanBuildFailure):
            route(inputs, failed)

    def test_source_and_route_inputs_invalidate_revision_and_cancellation_propagates(self):
        _, inputs, water = scenario()
        first = route(inputs, water)
        changed = replace(inputs, rivers=replace(inputs.rivers, max_path_cells=inputs.rivers.max_path_cells + 1))
        self.assertNotEqual(route(changed, water).ref.key, first.ref.key)
        _, _, other = scenario(lake=False)
        self.assertNotEqual(route(inputs, other).ref.key, first.ref.key)
        class Cancelled(Control):
            def raise_if_shutdown(self):
                raise RuntimeError("cancelled")
        with self.assertRaisesRegex(RuntimeError, "cancelled"):
            route(inputs, water, control=Cancelled())
