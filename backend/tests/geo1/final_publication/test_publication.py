from copy import replace
from unittest import TestCase
from unittest.mock import patch

from app.application.encoding.canonicalCodec import encode, decode
from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.hydrology.planning.assembly.hydrologyFactsAssembler import HydrologyFactsAssembler
from app.application.worldData.generators.hydrology.planning.assembly.final.nativeFacts import NativeFinalFactsJob
from app.application.worldData.generators.hydrology.water.planning.fine.publication import FineWaterPublicationJob
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyPlan
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from tests.geo1.native_final import test_facts as facts_fixture
from tests.geo1.native_relief.test_beds import relief_input
from tests.geo1.fine_water.test_fill import basin
from tests.geo1.source_projection.test_projection import resign
from tests.geo1.terrain_base.fixtures import Control


class PublicationTests(TestCase):
    def setUp(self):
        facts_fixture.NativeFinalTests.setUp(self)

    def publish(self, **changes):
        return HydrologyFactsAssembler().publish_fine(**(dict(world_uid="world", inputs=self.inputs,
            relief_inputs=relief_input(self.inputs), specs=(basin("lake", {(x, y) for y in range(10, 14) for x in range(10, 14)}),),
            before=self.before, expected_before=self.before.ref, water=self.water, expected_water=self.water.ref,
            routes=self.routes, expected_routes=self.routes.ref, river=self.river, expected_river=self.river.ref,
            control=Control()) | changes))

    def test_exact_publication_replays_and_retains_source_coverage_dependency(self):
        with patch.object(FineWaterPublicationJob, "admit_result", wraps=FineWaterPublicationJob.admit_result) as admit:
            result = self.publish()
        self.assertEqual(admit.call_count, 1)
        self.assertEqual({d.slot: d.ref for d in result.dependencies}, {"fine_water": self.water.ref,
            "pre_water_surface": self.before.ref, "hydrology_routes": self.routes.ref, "river_relief": self.river.ref})
        self.assertEqual(result.payload, facts_fixture.NativeFinalTests.final(self))
        self.assertEqual(decode(encode(result, SURFACE_MANIFEST), PlanEnvelope[GeoHydrologyPlan], SURFACE_MANIFEST), result)
        self.assertEqual(self.publish(), result)
        self.assertTrue(self.routes.diagnostics)
        self.assertTrue(set(self.routes.diagnostics) <= set(result.diagnostics))

    def test_stale_each_expected_ref_and_foreign_world_fail_before_facts(self):
        with patch.object(NativeFinalFactsJob, "assemble", side_effect=AssertionError("before admission")):
            for field in ("expected_before", "expected_water", "expected_routes", "expected_river"):
                with self.subTest(field=field), self.assertRaises(ValueError):
                    self.publish(**{field: replace(self.before.ref, key=replace(self.before.ref.key, world_uid="other"))})
            with self.assertRaises(ValueError):
                self.publish(world_uid="other")
            with self.assertRaises(ValueError):
                self.publish(routes=replace(self.routes, diagnostics=()))

    def test_mixed_source_graph_is_rejected_even_with_new_output_proof(self):
        bad = resign(self.river, dependencies=())
        with self.assertRaisesRegex(ValueError, "dependency graph"):
            self.publish(river=bad, expected_river=bad.ref)
        bad = resign(self.routes, dependencies=())
        with self.assertRaisesRegex(ValueError, "dependency graph"):
            self.publish(routes=bad, expected_routes=bad.ref)

    def test_changed_captured_inputs_specs_and_depths_fail(self):
        with patch.object(NativeFinalFactsJob, "assemble", side_effect=AssertionError("before admission")):
            for changes in (dict(inputs=replace(self.inputs, change_uid="other")), dict(specs=()),
                            dict(relief_inputs=relief_input(self.inputs, depth=3))):
                with self.subTest(changes=changes.keys()), self.assertRaises(ValueError):
                    self.publish(**changes)

    def test_water_error_blocks_before_facts(self):
        error = PlanDiagnostic(issue=FieldPathError(("water",), "failure"), disposition=PlanDiagnosticDisposition.ERROR)
        failed = resign(self.water, diagnostics=(*self.water.diagnostics, error))
        with self.assertRaises(PlanBuildFailure):
            self.publish(water=failed, expected_water=failed.ref)

    def test_cancellation(self):
        class Stop:
            def raise_if_shutdown(self):
                raise InterruptedError()
        with self.assertRaises(InterruptedError):
            self.publish(control=Stop())
