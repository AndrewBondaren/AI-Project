"""Reporting at the captured bundle boundary, including replay of real cached envelopes."""

from unittest import TestCase
from unittest.mock import Mock, patch

from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError
from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.planning.composition.hydrologyDiagnosticCollector import HydrologyDiagnosticCollector
from app.dataModel.hydrology import waterDiagnostics as water
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.hydrology.riverRouting import RiverPlanDiagnostic, RiverRouteDiagnostic, RiverRoutingCode, RiverRoutingFailure
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition as D
from tests.geo1.integration import test_revisions as geo
from tests.planning.consumers.test_wiring import Composition, Wait, capture, world


class ReportingTests(TestCase):
    def fixtures(self):
        pc = Composition()
        self.addCleanup(pc.service.shutdown)
        yield pc.assembler.prepare_captured_bundle, pc, capture(world())
        fixture = geo.GeoCapturedAssemblerTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        yield fixture.assembler.prepare_captured_geo_bundle, fixture, fixture.view

    def test_mixed_delivery_refusal_and_replay(self):
        ocean = water.WaterWorldOceanDiagnostic(issue=water.WaterWorldOcean(
            code=water.WaterDiagnosticCode.WATER_WORLD_OCEAN, world_uid="w", water_cells=2, world_cells=4),
            disposition=D.NOTICE)
        dry = water.WaterCannotHoldDiagnostic(issue=water.WaterCannotHold(
            code=water.WaterDiagnosticCode.WATER_CANNOT_HOLD, source_uid="dry", effective_level=0), disposition=D.ERROR)
        redirect = RiverPlanDiagnostic(issue=RiverRouteDiagnostic(world_uid="w", object_uid="r",
            requested_mouth=None, object_type=HydrologyConnectionType.RIVER, code=RiverRoutingCode.REDIRECTED,
            reason=RiverRoutingFailure.DRY_MOUTH, receiver_uid="sea", receiver_kind=BasinKind.SEA,
            receiver_cell=(0, 0)), disposition=D.FALLBACK)
        unrouted = RiverPlanDiagnostic(issue=RiverRouteDiagnostic(world_uid="w", object_uid="other",
            requested_mouth=None, object_type=HydrologyConnectionType.RIVER, code=RiverRoutingCode.NO_WATER_BODIES,
            reason=RiverRoutingFailure.DRY_MOUTH), disposition=D.ERROR)
        error, fallback, notice = (PlanDiagnostic(issue=geo.mismatch(d.value), disposition=d) for d in
                                   (D.ERROR, D.FALLBACK, D.NOTICE))
        for prepare, fixture, view in self.fixtures():
            build = fixture.registry.build

            def with_facts(contract, *args):
                result = build(contract, *args)
                if contract is fixture.handles.relief:
                    return result.model_copy(update={"diagnostics": (error, ocean, fallback, ocean)})
                if contract is fixture.handles.hydrology_routes:
                    return result.model_copy(update={"diagnostics": (redirect, notice, ocean, dry, unrouted)})
                return result

            with patch.object(fixture.registry, "build", side_effect=with_facts) as builds:
                for validate in (False, True):
                    for collect in (False, True):
                        ctx = ResolveContext(validate_only=validate, collect_only=collect)
                        collector = HydrologyDiagnosticCollector()
                        for repeat in range(2):
                            with self.subTest(entry=prepare.__name__, validate=validate, collect=collect, repeat=repeat):
                                deliver = Mock(wraps=collector.collect)
                                kwargs = dict(wait=Wait(), resolve_ctx=ctx,
                                              on_hydrology=deliver)
                                if validate:
                                    with self.assertRaises(UnresolvedModelError) as raised:
                                        prepare(view, **kwargs)
                                    self.assertEqual(tuple(raised.exception.issues), (error.issue,))
                                else:
                                    self.assertIsNotNone(prepare(view, **kwargs))
                                self.assertEqual(ctx.errors, [error.issue])
                                self.assertEqual(ctx.report.diagnostics, (fallback.issue,))
                                self.assertEqual(collector.facts, (ocean, redirect, dry, unrouted))
                                self.assertEqual(tuple(c.args[0] for c in deliver.call_args_list), collector.facts)
                                if repeat or validate or collect:
                                    builds.assert_not_called()
                                else:
                                    self.assertTrue(builds.called)
                                builds.reset_mock()
                failure = RuntimeError("delivery")
                with self.assertRaises(RuntimeError) as raised:
                    prepare(view, wait=Wait(), resolve_ctx=ResolveContext(collect_only=True),
                            on_hydrology=Mock(side_effect=failure))
                self.assertIs(raised.exception, failure)

    def test_build_failure_propagates_without_replaying_partial_facts(self):
        for prepare, fixture, view in self.fixtures():
            dry = water.WaterCannotHoldDiagnostic(issue=water.WaterCannotHold(
                code=water.WaterDiagnosticCode.WATER_CANNOT_HOLD, source_uid="dry", effective_level=0), disposition=D.ERROR)
            failure = PlanBuildFailure((), diagnostics=(dry,))
            method = "prepare_geo" if prepare == fixture.assembler.prepare_captured_geo_bundle else "prepare"
            callback = Mock()
            with patch.object(fixture.assembler, method, side_effect=failure), self.assertRaises(PlanBuildFailure) as raised:
                prepare(view, wait=Wait(), resolve_ctx=ResolveContext(), on_hydrology=callback)
            self.assertIs(raised.exception, failure)
            self.assertEqual(raised.exception.diagnostics, (dry,))
            callback.assert_not_called()
