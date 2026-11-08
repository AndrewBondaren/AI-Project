from unittest import TestCase

from pydantic import ValidationError

from app.application.encoding.boundedCanonicalDecode import decode_bounded
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.encoding.decodeLimits import DecodeLimits
from app.dataModel.hydrology import waterDiagnostics as w
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnosticDisposition as D
from app.encoding.canonicalCodec import CanonicalEncodingError, encode


class WaterDiagnosticsTests(TestCase):
    def test_admission_and_wire_roster(self):
        C = w.WaterDiagnosticCode
        cases = (
            (w.WaterPuddle, w.WaterPuddleDiagnostic, C.WATER_PUDDLE, D.ERROR, dict(source_uid="a", cell_count=1, minimum_cells=2)),
            (w.WaterCannotHold, w.WaterCannotHoldDiagnostic, C.WATER_CANNOT_HOLD, D.ERROR, dict(source_uid="a", effective_level=3)),
            (w.WaterTerrainUnresolved, w.WaterTerrainUnresolvedDiagnostic, C.WATER_TERRAIN_UNRESOLVED, D.ERROR, dict(world_uid="w", message="terrain")),
            (w.WaterNoOceanDepression, w.WaterNoOceanDepressionDiagnostic, C.WATER_NO_OCEAN_DEPRESSION, D.ERROR, dict(world_uid="w", default_water_level=0)),
            (w.WaterLevelSpill, w.WaterLevelSpillDiagnostic, C.WATER_LEVEL_SPILL, D.FALLBACK, dict(source_uid="a", requested_level=5, spill_limited_level=2)),
            (w.WaterLevelSuperseded, w.WaterLevelSupersededDiagnostic, C.WATER_LEVEL_SUPERSEDED, D.FALLBACK, dict(source_uid="a", declared_level=2, effective_level=8, parent_system_uid=None)),
            (w.WaterWorldOcean, w.WaterWorldOceanDiagnostic, C.WATER_WORLD_OCEAN, D.NOTICE, dict(world_uid="w", water_cells=2, world_cells=4)),
            (w.WaterPlacementRequired, w.WaterPlacementRequiredDiagnostic, C.WATER_PLACEMENT_REQUIRED, D.ERROR, dict(world_uid="w")),
        )
        for fact, carrier, code, expected, fields in cases:
            with self.subTest(code=code):
                issue = fact(code=code, **fields)
                for disposition in D:
                    if disposition != expected:
                        with self.assertRaises(ValidationError):
                            carrier(issue=issue, disposition=disposition)
                with self.assertRaises(ValidationError):
                    fact(code=code.value, **fields)
                diagnostic = carrier(issue=issue, disposition=expected)
                result = PlanBuildResult[int](payload=1, diagnostics=(diagnostic,))
                self.assertIs(type(result.diagnostics[0]), carrier)
                if code is C.WATER_PLACEMENT_REQUIRED:
                    with self.assertRaises(CanonicalEncodingError):
                        encode(diagnostic, SURFACE_MANIFEST)
                else:
                    wire = encode(diagnostic, SURFACE_MANIFEST)
                    self.assertEqual(decode_bounded(wire, carrier, SURFACE_MANIFEST,
                        limits=DecodeLimits(100000, 10000, 100, 1024)), diagnostic)

    def test_invalid_water_facts(self):
        C = w.WaterDiagnosticCode
        for fact, fields in (
            (w.WaterLevelSpill, dict(code=C.WATER_LEVEL_SPILL, source_uid="a", requested_level=2, spill_limited_level=2)),
            (w.WaterLevelSuperseded, dict(code=C.WATER_LEVEL_SUPERSEDED, source_uid="a", declared_level=2, effective_level=2, parent_system_uid=None)),
            (w.WaterPuddle, dict(code=C.WATER_PUDDLE, source_uid="a", cell_count=1, minimum_cells=1)),
            (w.WaterWorldOcean, dict(code=C.WATER_WORLD_OCEAN, world_uid="w", water_cells=1, world_cells=3)),
            (w.WaterCannotHold, dict(code=C.WATER_CANNOT_HOLD, source_uid="a", effective_level=True)),
        ):
            with self.subTest(fact=fact), self.assertRaises(ValidationError):
                fact(**fields)

    def test_protected_dry_a_continues_to_b_then_refuses_publication(self):
        from unittest.mock import patch
        from app.application.planning.service.planningService import PlanBuildFailure
        from app.application.worldData.generators.hydrology.water.planning.fine import execution
        from tests.geo1.fine_water.test_fill import basin, fill, source

        window, protected, topology = source(mountain=True)
        a = basin("A", {min(protected)})
        b = basin("B", {(x, y) for x in range(17, 25) for y in range(15, 22)} - protected)
        assemble = execution.assemble_water_bodies
        observed = []
        def capture(*args, **kwargs):
            result = assemble(*args, **kwargs)
            observed.extend(result.materialized.source_mapping.entries)
            return result
        with patch.object(execution, "assemble_water_bodies", side_effect=capture), self.assertRaises(PlanBuildFailure) as raised:
            fill(window, topology, (a, b))
        self.assertEqual([(e.source_uid, e.body_uids) for e in observed], [("A", ()), ("B", ("B",))])
        cause, = raised.exception.diagnostics
        self.assertEqual(cause.issue, w.WaterCannotHold(code=w.WaterDiagnosticCode.WATER_CANNOT_HOLD,
                                                       source_uid="A", effective_level=0))
        self.assertEqual(raised.exception.issues, ())

    def test_report_delivery_and_build_refusal(self):
        from unittest.mock import patch
        from app.application.jsonValidation.resolve import ResolveContext
        from app.application.planning.service.planningService import PlanBuildFailure
        from app.application.worldData.generators.hydrology.water import waterDiagnostics as reporting

        error = w.WaterCannotHoldDiagnostic(issue=w.WaterCannotHold(code=w.WaterDiagnosticCode.WATER_CANNOT_HOLD,
            source_uid="dry", effective_level=0), disposition=D.ERROR)
        spill = w.WaterLevelSpillDiagnostic(issue=w.WaterLevelSpill(code=w.WaterDiagnosticCode.WATER_LEVEL_SPILL,
            source_uid="wet", requested_level=3, spill_limited_level=2), disposition=D.FALLBACK)
        for ctx in (ResolveContext(), ResolveContext(collect_only=True), ResolveContext(validate_only=True)):
            with patch.object(reporting.logger, "warning", side_effect=OSError("unavailable")) as sink:
                report = reporting.report_water_diagnostics(ctx, (error, spill))
            self.assertEqual(report.blocking, (error,))
            self.assertEqual(report.continuations, (spill,))
            self.assertEqual(report.ordered, (error, spill))
            self.assertFalse(ctx.errors)
            self.assertEqual(sink.call_count, 0 if ctx.collect_only or ctx.validate_only else 2)
        for invalid in (spill, error.model_copy(update={"issue": spill.issue})):
            with self.assertRaises(ValueError):
                PlanBuildFailure((), diagnostics=(invalid,))

        with self.assertLogs(reporting.logger, level="WARNING") as captured:
            reversed_report = reporting.report_water_diagnostics(ResolveContext(), (spill, error))
        self.assertEqual(reversed_report.ordered, (spill, error))
        self.assertEqual(reversed_report.blocking, report.blocking)
        self.assertEqual(reversed_report.continuations, report.continuations)
        self.assertEqual([record.getMessage() for record in captured.records], ["water diagnostic"] * 2)
        self.assertEqual([record.diagnostic for record in captured.records],
                         [d.model_dump(mode="json", serialize_as_any=False) for d in (spill, error)])
        with self.assertRaises(ValidationError):
            w.WaterDiagnosticReport(ordered=(spill, error), blocking=(), continuations=(spill,), notices=())

    def test_foreign_field_issue_rejected_by_water_report_before_delivery(self):
        from unittest.mock import patch
        from app.application.jsonValidation.resolve import ResolveContext
        from app.application.worldData.generators.hydrology.water import waterDiagnostics as reporting
        from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic
        from tests.planning.probeIssues import probe_issue

        foreign = PlanDiagnostic(issue=probe_issue("foreign"), disposition=D.ERROR)
        with self.assertRaises(ValidationError):
            w.WaterDiagnosticReport(ordered=(foreign,), blocking=(foreign,), continuations=(), notices=())
        with patch.object(reporting.logger, "warning") as sink:
            with self.assertRaises(ValueError):
                reporting.report_water_diagnostics(ResolveContext(), (foreign,))
            sink.assert_not_called()

    def test_mismatch_requires_fallback_before_delivery(self):
        from unittest.mock import patch
        from app.application.jsonValidation.resolve import ResolveContext
        from app.application.worldData.generators.hydrology.water import waterDiagnostics as reporting
        from app.dataModel.hydrology.enums.basinKind import BasinKind
        from app.dataModel.hydrology.waterKindMismatchIssue import WaterKindMismatchIssue
        from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic

        def mismatch(uid, disposition):
            issue = WaterKindMismatchIssue.retained(uid, BasinKind.LAKE, BasinKind.SEA)
            return PlanDiagnostic(issue=issue, disposition=disposition)

        first = mismatch("B", D.FALLBACK)
        for disposition in (D.ERROR, D.NOTICE):
            bad = mismatch("A", disposition)
            facts = (first, bad)
            with self.subTest(disposition=disposition, boundary="constructor"):
                with self.assertRaisesRegex(ValidationError, "requires FALLBACK"):
                    w.WaterDiagnosticReport(ordered=facts, continuations=(first,),
                        blocking=(bad,) if disposition is D.ERROR else (),
                        notices=(bad,) if disposition is D.NOTICE else ())
            for ctx in (ResolveContext(), ResolveContext(collect_only=True), ResolveContext(validate_only=True)):
                with self.subTest(disposition=disposition, collect=ctx.collect_only, validate=ctx.validate_only):
                    with patch.object(reporting.logger, "warning") as sink:
                        with self.assertRaisesRegex(ValueError, "requires FALLBACK"):
                            reporting.report_water_diagnostics(ctx, facts)
                        sink.assert_not_called()
                    self.assertEqual(ctx.errors, [])
                    self.assertEqual(ctx.report.diagnostics, ())

        facts = (first, mismatch("A", D.FALLBACK))
        for ctx in (ResolveContext(), ResolveContext(collect_only=True), ResolveContext(validate_only=True)):
            with patch.object(reporting, "log_issues") as log:
                report = reporting.report_water_diagnostics(ctx, facts)
            self.assertEqual(report.ordered, facts)
            self.assertEqual(report.continuations, facts)
            self.assertTrue(all(type(d) is PlanDiagnostic and type(d.issue) is WaterKindMismatchIssue
                                for d in report.ordered))
            issues = [d.issue for d in facts]
            if ctx.collect_only or ctx.validate_only:
                log.assert_not_called()
                self.assertEqual(ctx.errors, issues)
            else:
                self.assertEqual([call.args[0] for call in log.call_args_list], [[issue] for issue in issues])
                self.assertEqual(ctx.errors, [])

    def test_apply_exposes_placement_refusal_and_returns_in_every_mode(self):
        from unittest.mock import patch
        from app.application.jsonValidation.resolve import ResolveContext
        from app.application.worldData.generators.hydrology.hydrologyGeneratorService import HydrologyGeneratorService
        from app.application.worldData.generators.hydrology.water import waterDiagnostics as reporting
        from tests.geo1.coastline.test_routing import coast
        from tests.hydrology_fixtures import hydro_world, flat_heightmap

        world = hydro_world(hydrology={"enabled": True, "declared_coastlines": [coast("source")],
            "default_seas": {"autoresolve_coastal_sea": False, "autoresolve_open_ocean": False},
            "default_lakes": {"autoresolve": False}})
        for ctx in (ResolveContext(), ResolveContext(validate_only=True), ResolveContext(collect_only=True)):
            with patch.object(reporting.logger, "warning") as sink:
                result = HydrologyGeneratorService().apply(world, [], flat_heightmap(0, 10, 0, 10), ctx=ctx)
            refusal, = result.water_diagnostics.blocking
            self.assertEqual(refusal.issue, w.WaterPlacementRequired(
                code=w.WaterDiagnosticCode.WATER_PLACEMENT_REQUIRED, world_uid=world.world_uid))
            self.assertFalse(ctx.errors)
            self.assertEqual(sink.call_count, int(not ctx.collect_only and not ctx.validate_only))
