from copy import replace
from unittest import TestCase
from unittest.mock import patch

from app.application.encoding.canonicalCodec import encode, decode
from app.application.planning.service.planFingerprints import output_fingerprint
from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.planning.preWater.terrainBasePlanner import PreWaterTerrainPlanner
from app.application.worldData.generators.terrain.planning.preWater.terrainBaseJob import PreWaterTerrainJob
from app.application.worldData.generators.terrain.planning.preWater.prepared.materialization import NaturalWindowJob
from app.application.worldData.generators.terrain.landcover.planning.preWaterHillHosts import PreWaterHillHostJob
from app.application.worldData.generators.terrain.hills import hillSelection
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.planning.identity.planKey import RegionPlanScope
from app.dataModel.terrain.planning.natural.preparedTerrain import PreparedNaturalTerrain, PREPARED_NATURAL
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from tests.geo1.natural_preparation.fixtures import ReadyPlans, values
from tests.geo1.terrain_base.fixtures import Control, prepare
from tests.geo1.hill_hosts.test_hosts import coverage
from tests.geo1.fine_water.test_fill import source, fill


def resign(envelope, **changes):
    changed = replace(envelope, **changes)
    return replace(changed, ref=replace(changed.ref, output_fingerprint=output_fingerprint(
        changed.payload, changed.dependencies, changed.diagnostics, SURFACE_MANIFEST)))


class PublicationTests(TestCase):
    def test_reused_preparation_publishes_exact_union_without_executing_preparation(self):
        plans = ReadyPlans(self)
        ready = plans.build()
        plans.backend.clear()
        areas = (coverage(0, 3, 0, 2), coverage(20, 23, 20, 22))
        union = RegionCoverage(region_uid="query", spans=tuple(s for area in areas for s in area.spans))
        expected, protected = prepare(plans.values, union)
        planner = PreWaterTerrainPlanner()
        before = encode(ready, SURFACE_MANIFEST)
        with patch.object(PreWaterTerrainJob, "__init__", side_effect=AssertionError("preparation")), \
             patch.object(PreWaterHillHostJob, "__init__", side_effect=AssertionError("host preparation")), \
             patch.object(PreWaterHillHostJob, "project_tile", side_effect=AssertionError("hosts")), \
             patch.object(hillSelection, "selected_hills", side_effect=AssertionError("selection")):
            window = planner.prepare_window(ready, expected_preparation=ready.ref, cells=union, control=Control())
            other = planner.prepare_window(ready, expected_preparation=ready.ref, cells=areas[0], control=Control())
            replay = planner.prepare_window(decode(before, PlanEnvelope[PreparedNaturalTerrain], SURFACE_MANIFEST),
                expected_preparation=ready.ref, cells=union, control=Control())
        self.assertEqual(dict(window.payload.surface_z), expected.surface_z)
        self.assertEqual(window.payload.protected_cells, protected)
        self.assertEqual(len(window.payload.surface_z), sum(s.x1-s.x0 for s in union.spans))
        self.assertEqual(window, replay)
        self.assertNotEqual(window.ref, other.ref)
        self.assertEqual({d.slot: d.ref for d in window.dependencies},
                         {**{d.slot: d.ref for d in ready.dependencies}, PREPARED_NATURAL: ready.ref})
        self.assertEqual(encode(ready, SURFACE_MANIFEST), before)

    def test_identity_follows_prepared_revision_even_when_local_geometry_is_equal(self):
        plans = ReadyPlans(self, values(mountain=False))
        ready = plans.build()
        base, relief, support = plans.values[:3]
        self.assertTrue(support.materials)
        newer = plans.build((base, relief, replace(support, materials=())))
        self.assertEqual(ready.payload, newer.payload)
        self.assertNotEqual(ready.ref.key, newer.ref.key)
        planner = PreWaterTerrainPlanner()
        a = planner.prepare_window(ready, expected_preparation=ready.ref, cells=coverage(), control=Control())
        b = planner.prepare_window(newer, expected_preparation=newer.ref, cells=coverage(), control=Control())
        self.assertEqual(a.payload, b.payload)
        self.assertNotEqual(a.ref, b.ref)

    def test_stale_tampered_metadata_and_source_closure_fail_before_geometry(self):
        ready = ReadyPlans(self).build()
        changed_light = replace(ready.payload.light, base_surface_z=tuple(
            (c, z+1) for c, z in ready.payload.light.base_surface_z))
        tampered = replace(ready, payload=replace(ready.payload, light=changed_light))
        foreign = replace(ready.dependencies[0], ref=replace(ready.dependencies[0].ref,
            key=replace(ready.dependencies[0].ref.key, world_uid="foreign")))
        variants = (tampered, resign(ready, dependencies=ready.dependencies[:1]),
            resign(ready, dependencies=(foreign, *ready.dependencies[1:])),
            replace(ready, ref=replace(ready.ref, key=replace(ready.ref.key, contract_id="wrong.contract"))),
            replace(ready, ref=replace(ready.ref, key=replace(ready.ref.key, scope=RegionPlanScope(region_uid="other")))))
        with patch.object(NaturalWindowJob, "materialize", side_effect=AssertionError("geometry before admission")):
            for candidate in variants:
                with self.subTest(candidate=candidate.ref), self.assertRaises(ValueError):
                    PreWaterTerrainPlanner().prepare_window(candidate, expected_preparation=candidate.ref,
                        cells=coverage(), control=Control())
            with self.assertRaisesRegex(ValueError, "revision"):
                PreWaterTerrainPlanner().prepare_window(ready, expected_preparation=variants[-1].ref,
                    cells=coverage(), control=Control())

    def test_upstream_error_and_cancellation_cannot_publish_a_window(self):
        ready = ReadyPlans(self).build()
        error = PlanDiagnostic(issue=FieldPathError(("source",), "unresolved"),
                               disposition=PlanDiagnosticDisposition.ERROR)
        failed = resign(ready, diagnostics=(error,))
        class Stop:
            def raise_if_shutdown(self):
                raise InterruptedError("cancelled")
        with patch.object(NaturalWindowJob, "materialize", side_effect=AssertionError("geometry")):
            with self.assertRaises(PlanBuildFailure):
                PreWaterTerrainPlanner().prepare_window(failed, expected_preparation=failed.ref,
                    cells=coverage(), control=Control())
            with self.assertRaises(InterruptedError):
                PreWaterTerrainPlanner().prepare_window(ready, expected_preparation=ready.ref,
                    cells=coverage(), control=Stop())

    def test_fine_water_rejects_missing_or_foreign_prepared_proof(self):
        window, _, topology = source(hills=False)
        deps = tuple(d for d in window.dependencies if d.slot != PREPARED_NATURAL)
        missing = resign(window, dependencies=deps)
        dependency = next(d for d in window.dependencies if d.slot == PREPARED_NATURAL)
        wrong = replace(dependency, ref=replace(dependency.ref,
            key=replace(dependency.ref.key, contract_id="wrong.natural")))
        foreign = resign(window, dependencies=tuple(wrong if d.slot == PREPARED_NATURAL else d for d in window.dependencies))
        for candidate in (missing, foreign):
            with self.subTest(candidate=candidate.ref), self.assertRaisesRegex(ValueError, "prepared|preparation"):
                fill(candidate, topology)
