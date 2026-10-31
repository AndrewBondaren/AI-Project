from copy import replace
from unittest import TestCase
from unittest.mock import patch

from app.application.encoding.canonicalCodec import encode, decode, digest
from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.planning.preWater.prepared.preparation import NaturalPreparationJob
from app.application.worldData.generators.terrain.planning.preWater.terrainBasePlanner import PreWaterTerrainPlanner
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.terrain.planning.natural.preparedTerrain import PreparedNaturalTerrain
from app.dataModel.terrain.hillShape import HillShape
from app.dataModel.validation.immutableValue import validate_immutable
from tests.geo1.hill_hosts.test_hosts import coverage
from tests.geo1.terrain_base.fixtures import prepare, Control
from tests.geo1.natural_preparation.fixtures import ReadyPlans, values


# Captured from the original full calculation BEFORE extracting the selection kernel.
GOLDEN = {
    ("circle", False): "c2df92d8fd1ff1f3a36a092ae7b649bd3ba88a2c0b4fc8a3e1bce597f29de903",
    ("circle", True): "8f89e5e479695f59a4f6b56193328c60a7914a25ef2448c82fa7e07bf862db57",
    ("oval", False): "070265a84b9bef9dcc8dff267f258d354473e3018743704f584b077574c842d5",
    ("oval", True): "baa9e0d54221cc44305927bb3082ba57d5bc5feaea134f1981169844e29e7698",
    ("double_circle", False): "dc888c3906ab231516e0d3603793585feddc326589a69fc9cf51b4d53a5ba4e9",
    ("double_circle", True): "3ee83eb8f68298dfec7ed0259ce062b109478f594d010e3ce9122c4a14804784",
    ("double_oval", False): "16cdd5139f76913693dbf36b68b64697727dadc4b93e25c89fbe2df44c96863a",
    ("double_oval", True): "05959fcb37b0a115afb61406300b8865253fdc5c5a29c3c23b150324bde555d3",
}


class PreparationTests(TestCase):
    def test_original_full_geometry_digests_and_prepared_full_geometry_match(self):
        planner = PreWaterTerrainPlanner()
        for shape in HillShape:
            for mountain in (False, True):
                with self.subTest(shape=shape, mountain=mountain):
                    v = values(shape=shape, mountain=mountain)
                    full, protected = prepare(v)
                    fingerprint = digest((tuple(sorted(full.surface_z.items(), key=lambda c: (c[0][1], c[0][0]))),
                                          tuple(sorted(protected))), SURFACE_MANIFEST).hex()
                    self.assertEqual(fingerprint, GOLDEN[shape.value, mountain])
                    ready = planner.prepare_revision("world", *v, control=Control()).payload
                    observed = planner.materialize(ready, cells=coverage(0, 32, 0, 32), control=Control())
                    self.assertEqual(dict(observed.surface_z), full.surface_z)
                    self.assertEqual(observed.protected_cells, protected)

    def test_service_reuses_revision_across_windows_and_ready_survives_cache_clear(self):
        plans = ReadyPlans(self)
        original = NaturalPreparationJob.prepare
        with patch.object(NaturalPreparationJob, "prepare", autospec=True, side_effect=original) as producer:
            ready = plans.build()
            self.assertEqual(plans.build(), ready)
            self.assertEqual(producer.call_count, 1)
            plans.backend.clear()
            planner = PreWaterTerrainPlanner()
            for cells in (coverage(1, 3, 1, 4), coverage(18, 22, 20, 23)):
                planner.materialize(ready.payload, cells=cells, control=Control())
            self.assertEqual(producer.call_count, 1)

    def test_codec_immutability_and_input_invalidation(self):
        plans = ReadyPlans(self)
        ready = plans.build()
        encoded = encode(ready, SURFACE_MANIFEST)
        self.assertEqual(decode(encoded, PlanEnvelope[PreparedNaturalTerrain], SURFACE_MANIFEST), ready)
        validate_immutable(ready)
        with self.assertRaises((TypeError, ValueError)):
            ready.payload.tiles[0].gx = 99
        base, relief, support = plans.values[:3]
        changed = replace(support, terrain_entries=tuple(replace(e, hills=replace(e.hills, height=e.hills.height+1))
                          if e.hills else e for e in support.terrain_entries))
        newer = plans.build((base, relief, changed))
        self.assertNotEqual(newer.ref.key, ready.ref.key)
        self.assertEqual(encode(ready, SURFACE_MANIFEST), encoded)

    def test_cancellation_and_inconsistent_capture_fail_before_publication(self):
        class Stop:
            def raise_if_shutdown(self):
                raise InterruptedError("cancelled")
        planner = PreWaterTerrainPlanner()
        with self.assertRaises(InterruptedError):
            planner.prepare_revision("world", *values(), control=Stop())
        v = values()
        v[1] = replace(v[1], seed=v[1].seed+1)
        with self.assertRaisesRegex(ValueError, "coherent"):
            planner.prepare_revision("world", *v, control=Control())

    def test_upstream_error_cannot_publish_a_ready_natural_revision(self):
        v = values()
        v[3] = replace(v[3], diagnostics=(PlanDiagnostic(issue=FieldPathError(("climate",), "unresolved source"),
            disposition=PlanDiagnosticDisposition.ERROR),))
        plans = ReadyPlans(self, v)
        with self.assertRaises(PlanBuildFailure):
            plans.build()
