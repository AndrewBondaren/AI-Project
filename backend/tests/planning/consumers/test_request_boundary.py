"""PC-11.3 capture-only reporting and mandatory operation inputs."""

import unittest
from unittest.mock import Mock, patch

from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError
from app.application.worldData.materialize.worldSurfaceMaterializationOrchestrator import (
    WorldSurfaceMaterializationOrchestrator,
)
from app.application.worldData.planning.composition.surfacePlanningCapture import SurfacePlanningCapture
from app.application.worldData.planning.composition.surfacePlanningEntry import SurfacePlanningEntry
from app.application.worldData.planning.contracts.surfacePlanningView import SurfacePlanningViewKind
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from tests.planning.consumers.test_wiring import Composition, Wait, capture, world


class ProbeTests(unittest.TestCase):
    def test_probe_reports_diagnostics_once_without_preparing(self):
        for no_extent in (False, True):
            for validate_only, collect_only in ((False, False), (False, True), (True, False)):
                with self.subTest(no_extent=no_extent, validate=validate_only, collect=collect_only):
                    source = world(world_bounds=None) if no_extent else world()
                    baseline = capture(world())
                    issue = FieldPathError(("probe",), "fallback", code="probe_fallback")
                    notice = PlanDiagnostic(issue=FieldPathError(("probe",), "notice"),
                        disposition=PlanDiagnosticDisposition.NOTICE)
                    fallback = PlanDiagnostic(issue=issue, disposition=PlanDiagnosticDisposition.FALLBACK)
                    planning = Mock()
                    entry = SurfacePlanningEntry(planning, SurfacePlanningCapture())
                    ctx = ResolveContext(validate_only=validate_only, collect_only=collect_only)
                    # Model a producer that has already reported the issue to the request.
                    ctx.errors.append(issue)
                    mode = ResolutionMode.VALIDATE_ONLY if validate_only else ResolutionMode.RUNTIME
                    with patch("app.application.worldData.planning.composition.surfacePlanningCapture.resolve_base_profiles",
                            return_value=(baseline.climate_base.profiles, (fallback, notice, notice))), patch(
                            "app.application.worldData.planning.composition.surfacePlanningAssembler.logging.getLogger") as logger:
                        if validate_only:
                            with self.assertRaises(UnresolvedModelError):
                                entry.probe_extent(source, [], mode=mode, mountain_templates=(), resolve_ctx=ctx)
                        else:
                            status = entry.probe_extent(source, [], mode=mode,
                                mountain_templates=(), resolve_ctx=ctx)
                            self.assertEqual(status, SurfacePlanningViewKind.NO_EXTENT if no_extent
                                else SurfacePlanningViewKind.READY)
                        self.assertEqual(ctx.errors, [issue])
                        self.assertEqual(logger.return_value.info.call_count, 0 if collect_only else 1)
                    planning.prepare.assert_not_called()

    def test_prepare_reports_capture_notice_once_on_cache_hit_and_miss(self):
        composition = Composition()
        self.addCleanup(composition.service.shutdown)
        source = world()
        baseline = capture(source)
        notice = PlanDiagnostic(issue=FieldPathError(("probe",), "notice"),
            disposition=PlanDiagnosticDisposition.NOTICE)
        entry = SurfacePlanningEntry(composition.assembler, SurfacePlanningCapture())
        with patch("app.application.worldData.planning.composition.surfacePlanningCapture.resolve_base_profiles",
                return_value=(baseline.climate_base.profiles, (notice, notice))):
            for hit in (False, True):
                with self.subTest(hit=hit), patch.object(composition.registry, "build",
                        wraps=composition.registry.build) as builds, patch(
                        "app.application.worldData.planning.composition.surfacePlanningAssembler.logging.getLogger") as logger:
                    entry.require_plan_inputs(source, [], wait=Wait())
                    self.assertEqual(logger.return_value.info.call_count, 1)
                    self.assertEqual(builds.call_count, 0 if hit else 8)

    def test_bootstrap_preview_probes_without_preparing(self):
        planning, pack = Mock(), Mock()
        owner = WorldSurfaceMaterializationOrchestrator(pack, detailed=Mock(),
            planning=planning, capture=SurfacePlanningCapture())
        pack.tile_planner.plan.return_value = []
        self.assertEqual(owner.plan_bootstrap_tiles(world(), []), [])
        with self.assertRaisesRegex(ValueError, "unavailable"):
            owner.plan_bootstrap_tiles(world(world_bounds=None), [])
        self.assertEqual(pack.tile_planner.plan.call_count, 1)
        planning.prepare.assert_not_called()


if __name__ == "__main__":
    unittest.main()
