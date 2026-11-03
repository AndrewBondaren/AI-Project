from copy import replace
from unittest import TestCase

from app.application.planning.service.planFingerprints import input_fingerprint
from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.designedWater.preparation.nativePlacementDependencies import (
    admit_native_placement_dependencies,
)
from app.application.worldData.generators.terrain.planning.preWater.terrainWindowJob import PRE_WATER_WINDOW
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.common import PlacementPhase
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.planning.identity.planKey import RegionPlanScope
from app.dataModel.surfacePlanning.surfacePlanBindings import geo_surface_plan_binding
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.terrain.regions.terrainRegionExtent import TerrainRegionExtent
from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionPlan, TerrainRegionsSnapshot
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from tests.geo1.fine_water.fixtures import physical_inputs
from tests.geo1.fine_water.test_fill import source
from tests.geo1.hill_hosts.test_hosts import coverage
from tests.geo1.integration.support.fixtures import seal
from tests.geo1.integration.support.pipeline import view
from tests.geo1.source_projection.test_projection import resign
from tests.geo1.terrain_base.fixtures import Control


def rekey(envelope, **changes):
    return replace(envelope, ref=replace(envelope.ref, key=replace(envelope.ref.key, **changes)))


def window_with_dependencies(window, deps):
    key = window.ref.key
    fingerprint = input_fingerprint(PRE_WATER_WINDOW, key.world_uid, key.scope,
                                    window.payload.coverage, deps, SURFACE_MANIFEST)
    return rekey(resign(window, dependencies=deps), input_fingerprint=fingerprint)


class NativePlacementDependencyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.window, _, topology = source(hills=False)
        physical = physical_inputs(topology)
        cls.inputs = replace(view().water_placement, topology=physical.topology, grid=physical.grid,
                             declared_world_bounds=physical.topology.bounds)
        plan = TerrainRegionPlan(snapshot=TerrainRegionsSnapshot(world_uid="world", snapshot_uid="regions",
            world_region=TerrainRegionExtent(region_uid="world", generation_area_fine2=1), regions=()),
            coverages=(coverage(31, 32, 31, 32),))
        cls.regions = seal(geo_surface_plan_binding(SurfacePlanSlot.TERRAIN_REGIONS), plan)
        cls.batch = PlacementBatchV2(world_uid="world", snapshot_uid="regions",
            snapshot_revision=cls.window.ref.output_fingerprint, phase=PlacementPhase.PRE_RELIEF,
            topology=topology, accepted=(), objects=())

    def admit(self, *, before=None, regions=None, **changes):
        before = self.window if before is None else before
        regions = self.regions if regions is None else regions
        args = dict(before=before, expected_before=before.ref, regions=regions, expected_regions=regions.ref,
                    inputs=self.inputs, batch=replace(self.batch, snapshot_revision=before.ref.output_fingerprint),
                    control=Control())
        return admit_native_placement_dependencies(**(args | changes))

    def test_exact_sorted_refs(self):
        self.assertEqual(self.admit(), (PlanDependency(slot="pre_water_surface", ref=self.window.ref),
                                        PlanDependency(slot="terrain_regions", ref=self.regions.ref)))

    def test_refs_and_output_proofs_on_both_inputs(self):
        for name, envelope in (("before", self.window), ("regions", self.regions)):
            stale = rekey(envelope, input_fingerprint=b"s" * 32)
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "expected dependency revision"):
                self.admit(**{"expected_" + name: stale.ref})
            bad = replace(envelope, ref=replace(envelope.ref, output_fingerprint=b"x" * 32))
            with self.assertRaisesRegex(ValueError, "output proof"):
                self.admit(**{name: bad})
            with self.assertRaisesRegex(ValueError, "contract or version"):
                self.admit(**{name: rekey(envelope, algorithm_version=99)})

    def test_world_scope_and_window_input_proof(self):
        for key in (dict(world_uid="foreign"), dict(scope=RegionPlanScope(region_uid="area"))):
            with self.assertRaisesRegex(ValueError, "world and plan scope"):
                self.admit(regions=rekey(self.regions, **key))
        with self.assertRaisesRegex(ValueError, "coverage input proof"):
            self.admit(before=rekey(self.window, input_fingerprint=b"x" * 32))

    def test_dependency_graph(self):
        deps = self.window.dependencies
        with self.assertRaisesRegex(ValueError, "dependency slots"):
            self.admit(before=window_with_dependencies(self.window, deps[1:]))
        with self.assertRaisesRegex(ValueError, "dependency slots"):
            self.admit(regions=resign(self.regions, dependencies=deps[:1]))
        for changes, error in ((dict(algorithm_version=99), "contract or version"),
                               (dict(scope=RegionPlanScope(region_uid="foreign")), "upstream world or scope")):
            ref = deps[0].ref
            changed = replace(deps[0], ref=replace(ref, key=replace(ref.key, **changes)))
            with self.assertRaisesRegex(ValueError, error):
                self.admit(before=window_with_dependencies(self.window, (changed, *deps[1:])))

    def test_snapshot_bindings_and_phase(self):
        for change in (dict(snapshot_revision=self.regions.ref.output_fingerprint), dict(snapshot_uid="other")):
            with self.assertRaisesRegex(ValueError, "region snapshot"):
                self.admit(batch=replace(self.batch, **change))
        plan = self.regions.payload
        foreign = replace(plan, snapshot=replace(plan.snapshot, world_uid="other"))
        with self.assertRaisesRegex(ValueError, "region snapshot"):
            self.admit(regions=resign(self.regions, payload=foreign))
        with self.assertRaisesRegex(ValueError, "joint pre-relief"):
            self.admit(batch=replace(self.batch, phase=PlacementPhase.DEPENDENT))

    def test_signed_error_diagnostics_from_either_input(self):
        for name, envelope in (("before", self.window), ("regions", self.regions)):
            issue = FieldPathError((name,), "upstream failed")
            diagnostic = PlanDiagnostic(issue=issue, disposition=PlanDiagnosticDisposition.ERROR)
            with self.assertRaises(PlanBuildFailure) as caught:
                self.admit(**{name: resign(envelope, diagnostics=(diagnostic,))})
            self.assertEqual(caught.exception.issues, (issue,))

    def test_coarse_batch_and_double_lift(self):
        with self.assertRaisesRegex(ValueError, "captured fine frame"):
            self.admit(batch=replace(self.batch, topology=self.inputs.topology))
        already_fine = self.batch.topology
        with self.assertRaisesRegex(ValueError, "captured fine frame"):
            self.admit(inputs=replace(self.inputs, topology=already_fine, declared_world_bounds=already_fine.bounds))

    def test_partial_window_vertical_bounds_and_region_spans(self):
        partial, _, _ = source(cells=coverage(0, 1, 0, 1), hills=False)
        with self.assertRaisesRegex(ValueError, "complete fine window"):
            self.admit(before=partial)
        window = self.window.payload
        cell, _ = window.surface_z[0]
        tall = replace(window, surface_z=((cell, self.inputs.z_max + 1), *window.surface_z[1:]))
        with self.assertRaisesRegex(ValueError, "vertical bounds"):
            self.admit(before=resign(self.window, payload=tall))
        for outside in (coverage(31, 32, 32, 33), coverage(32, 33, 31, 32)):
            plan = replace(self.regions.payload, coverages=(outside,))
            with self.assertRaisesRegex(ValueError, "region span"):
                self.admit(regions=resign(self.regions, payload=plan))

    def test_shutdown_during_height_scan(self):
        class Stop:
            checks = 0

            def raise_if_shutdown(self):
                self.checks += 1
                if self.checks == 20:
                    raise InterruptedError()

        with self.assertRaises(InterruptedError):
            self.admit(control=Stop())
