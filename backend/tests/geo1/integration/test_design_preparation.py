"""Joint J05–J07 execution, without activating legacy water transports."""

from unittest import TestCase
from unittest.mock import Mock, patch

from app.application.planning.service.planningService import PlanBuildFailure, PlanWaitCancelled
from app.application.worldData.generators.terrain.designedWater.preparation.designPreparation import prepare_designed_water
from app.application.worldData.generators.terrain.designedWater.strategies.strategyFactory import DesignedWaterStrategyFactory
from app.application.worldData.placement.lifecycle.session import PlacementSession
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.common import DependencyRelation, PlacementPhase
from app.dataModel.placement.intent import PlacementDependency
from app.dataModel.placement.lifecycle.header import PlacementHeader
from app.dataModel.placement.result import DisabledPlacement, ResolvedPlacementV2, UnresolvedPlacementV2
from app.dataModel.policy.policyEnums import PolicyState
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from tests.geo1.contracts.strategies import test_dispatch_budget as joins
from tests.geo1.contracts import test_placement_lifecycle as lifecycle


class DesignPreparationTests(TestCase):
    def case(self, kind=Strategy.AUTHORED_REGION):
        return joins.PreparedWaterAdmissionTests().case(kind)

    def arguments(self, case, *, competitors=()):
        _, value, _, intent, admission = case
        batch = PlacementBatchV2(world_uid="world", snapshot_uid="pre-relief",
            snapshot_revision=value.pre_hydrology_ref.output_fingerprint, phase=PlacementPhase.PRE_RELIEF,
            topology=value.topology, objects=(admission, *competitors), accepted=())
        return dict(batch=batch, water_intents=(intent,), pre_hydrology=value.pre_hydrology,
            grid=value.grid, seed_root=value.seed_root, prepare_input=Mock(return_value=value),
            prepare_competitor=Mock(side_effect=AssertionError("unexpected competitor")),
            strategies=DesignedWaterStrategyFactory.builtins(), selection_policy=WaterFieldSelectionPolicy(),
            control=Mock())

    def test_all_four_strategies_use_main_path_once_and_preserve_preparation(self):
        for kind in Strategy:
            case = self.case(kind)
            args = self.arguments(case)
            before = case[1].model_dump(), args["batch"].model_dump()
            strategy = args["strategies"].get(kind)
            with self.subTest(kind=kind), patch.object(strategy, "design", wraps=strategy.design) as design:
                preparations, result = prepare_designed_water(**args)
                design.assert_called_once()
                args["prepare_input"].assert_called_once_with(case[4])
                self.assertEqual(preparations, (case[2],))
                self.assertIsInstance(result.results[0], ResolvedPlacementV2)
                self.assertEqual(result.results[0].prepared, case[0].bind_admission(case[1], case[2],
                    intent=case[3], admission=case[4]))
                self.assertEqual((case[1].model_dump(), args["batch"].model_dump()), before)

    def test_water_and_competitor_are_prepared_before_the_same_heap_and_replay(self):
        case = self.case()
        competitor = lifecycle.member("competitor", priority=20)
        args = self.arguments(case, competitors=(competitor,))
        cells = case[2].candidates[0].footprint.cells
        args["prepare_competitor"] = Mock(side_effect=lambda obj: lifecycle.prepared(obj, cells=cells))
        step = PlacementSession.step
        def inspect(session):
            self.assertEqual(args["prepare_input"].call_count, 1)
            self.assertEqual(args["prepare_competitor"].call_count, 1)
            return step(session)
        with patch.object(PlacementSession, "step", inspect):
            preparations, result = prepare_designed_water(**args)
        outcomes = {o.identity.region_uid: o for o in result.results}
        self.assertIsInstance(outcomes["competitor"], ResolvedPlacementV2)
        self.assertIsInstance(outcomes[case[3].identity.region_uid], UnresolvedPlacementV2)
        self.assertEqual(preparations, (case[2],))  # retain loser's floor/metadata/notices
        args["batch"] = args["batch"].model_copy(update={"objects": tuple(reversed(args["batch"].objects))})
        self.assertEqual(prepare_designed_water(**args), (preparations, result))

    def test_disabled_and_unresolved_admissions_never_prepare_geometry(self):
        case = self.case()
        from tests.geo1.placement_policy.fixtures import bind, execute
        disabled = execute(bind(source=case[1].source, enabled=False, strategy=case[1].strategy))
        unresolved = case[4].decision.model_copy(update={"state": PolicyState.UNRESOLVED,
            "issues": (FieldPathError(("source",), "missing evidence", code="missing"),)})
        for decision, expected in ((disabled, DisabledPlacement), (unresolved, UnresolvedPlacementV2)):
            args = self.arguments(case)
            obj = case[4].model_copy(update={"decision": decision})
            args["batch"] = args["batch"].model_copy(update={"objects": (obj,)})
            preparations, result = prepare_designed_water(**args)
            self.assertEqual(preparations, ())
            self.assertIsInstance(result.results[0], expected)
            args["prepare_input"].assert_not_called()

    def dependent_case(self, case, target="support", *, waiting=False):
        owner, value, design, intent, admission = case
        intent = intent.model_copy(update={"dependencies": (PlacementDependency(target_uid=target,
            relation=DependencyRelation.RESOLVED),)})
        decision = admission.decision.model_copy(update={"state": PolicyState.WAITING_SUPPORT,
            "waiting_supports": (target,)}) if waiting else admission.decision
        return owner, value, design, intent, admission.model_copy(update={
            "header": PlacementHeader.from_intent(intent), "decision": decision})

    def test_support_resume_passes_current_decision_and_designs_only_after_support(self):
        original = self.case()
        case = self.dependent_case(original, waiting=True)
        support = lifecycle.member("support", priority=10)
        args = self.arguments(case, competitors=(support,))
        events = []
        args["prepare_competitor"] = lambda obj: (events.append("support") or lifecycle.prepared(obj, cells=((0, 0),)))
        def resume(header, causes):
            self.assertEqual(causes[0].region_uid, "support")
            events.append("resume")
            return original[4].decision
        def ready(obj):
            events.append("water")
            self.assertEqual(obj.decision, original[4].decision)
            return original[1]
        args.update(prepare_input=ready, reevaluate_support=resume)
        preparations, result = prepare_designed_water(**args)
        self.assertEqual(events, ["support", "resume", "water"])
        self.assertEqual(len(preparations), 1)
        self.assertTrue(all(isinstance(o, ResolvedPlacementV2) for o in result.results))

    def test_missing_or_failed_support_never_invokes_water_input(self):
        for present in (False, True):
            case = self.dependent_case(self.case())
            support = lifecycle.member("support")
            args = self.arguments(case, competitors=(support,) if present else ())
            args["prepare_competitor"] = Mock(side_effect=PlanBuildFailure((FieldPathError(
                ("support",), "cannot prepare", code="support_failure"),)))
            preparations, result = prepare_designed_water(**args)
            water = next(o for o in result.results if o.identity.region_uid == case[3].identity.region_uid)
            self.assertIsInstance(water, UnresolvedPlacementV2)
            self.assertEqual(water.causes[0].region_uid, "support")
            self.assertEqual(preparations, ())
            args["prepare_input"].assert_not_called()

    def test_source_failure_is_terminal_and_independent_competitor_finishes(self):
        case = self.case()
        competitor = lifecycle.member("independent")
        child = lifecycle.member("child", targets=(case[3].identity.region_uid,))
        args = self.arguments(case, competitors=(competitor, child))
        args["prepare_input"].side_effect = PlanBuildFailure((FieldPathError(("water",), "empty", code="empty_target"),))
        args["prepare_competitor"] = Mock(side_effect=lambda obj: lifecycle.prepared(obj, cells=((0, 0),)))
        preparations, result = prepare_designed_water(**args)
        outcomes = {o.identity.region_uid: o for o in result.results}
        self.assertEqual(preparations, ())
        self.assertIsInstance(outcomes["independent"], ResolvedPlacementV2)
        self.assertIsInstance(outcomes["child"], UnresolvedPlacementV2)
        self.assertIn("empty_target", outcomes[case[3].identity.region_uid].diagnostics[0].detail)
        args["prepare_competitor"].assert_called_once_with(competitor)

    def test_stale_batch_or_wrong_intent_fails_before_any_source_preparation(self):
        case = self.case()
        for change in (dict(snapshot_revision=b"s"*32), dict(world_uid="other"), dict(phase=PlacementPhase.DEPENDENT)):
            args = self.arguments(case)
            args["batch"] = args["batch"].model_copy(update=change)
            with self.assertRaises((PlanBuildFailure, ValueError)):
                prepare_designed_water(**args)
            args["prepare_input"].assert_not_called()
        for intents in ((case[3], case[3]), (case[3].model_copy(update={"dependencies": (
                PlacementDependency(target_uid="other", relation=DependencyRelation.RESOLVED),)}),)):
            args = self.arguments(case)
            args["water_intents"] = intents
            with self.assertRaises(PlanBuildFailure):
                prepare_designed_water(**args)
            args["prepare_input"].assert_not_called()

    def test_foreign_ready_scope_fails_before_strategy_execution(self):
        case = self.case()
        ref = case[1].pre_hydrology_ref.model_copy(update={"output_fingerprint": b"s"*32})
        for update in (dict(seed_root="other"), dict(
                pre_hydrology=case[1].pre_hydrology.model_copy(update={"ref": ref}),
                geometry=case[1].geometry.model_copy(update={"pre_hydrology_ref": ref}))):
            args = self.arguments(case)
            args["prepare_input"].return_value = type(case[1]).model_validate(case[1].model_copy(update=update))
            with patch.object(args["strategies"], "get", side_effect=AssertionError("stale design")):
                preparations, result = prepare_designed_water(**args)
                self.assertEqual(preparations, ())
                self.assertIsInstance(result.results[0], UnresolvedPlacementV2)

    def test_multiple_water_sources_share_one_universe_and_retain_both_designs(self):
        cases = [self.case(), joins.PreparedWaterAdmissionTests().case(lake=True)]
        renamed = []
        for owner, value, design, intent, admission in cases:
            intent = intent.model_copy(update={"identity": intent.identity.model_copy(update={
                "region_uid": value.metadata.source_uid})})
            renamed.append((owner, value, design, intent, admission.model_copy(update={
                "header": PlacementHeader.from_intent(intent)})))
        args = self.arguments(renamed[0], competitors=(renamed[1][4],))
        args["water_intents"] = tuple(case[3] for case in renamed)
        inputs = {case[1].metadata.source_uid: case[1] for case in renamed}
        args["prepare_input"] = Mock(side_effect=lambda obj: inputs[obj.header.identity.source_uid])
        preparations, result = prepare_designed_water(**args)
        self.assertEqual({p.metadata.source_uid for p in preparations}, set(inputs))
        self.assertEqual(args["prepare_input"].call_count, 2)
        self.assertEqual(sum(isinstance(o, ResolvedPlacementV2) for o in result.results), 1)
        self.assertEqual(sum(isinstance(o, UnresolvedPlacementV2) for o in result.results), 1)
        args["prepare_competitor"].assert_not_called()

    def test_cycle_is_settled_without_input_or_geometry(self):
        case = self.dependent_case(self.case())
        support = lifecycle.member("support", targets=(case[3].identity.region_uid,))
        args = self.arguments(case, competitors=(support,))
        preparations, result = prepare_designed_water(**args)
        self.assertEqual(preparations, ())
        self.assertTrue(all(isinstance(o, UnresolvedPlacementV2) for o in result.results))
        args["prepare_input"].assert_not_called()
        args["prepare_competitor"].assert_not_called()

    def test_shutdown_after_design_stops_before_geometry_and_spatial_resolution(self):
        from app.application.worldData.generators.terrain.designedWater.preparation.placementPreparation import DesignedWaterPlacementPreparer
        case = self.case()
        args = self.arguments(case)
        strategy = args["strategies"].get(case[1].strategy)
        original = strategy.design
        def stop_after_design(value):
            draft = original(value)
            args["control"].raise_if_shutdown.side_effect = PlanWaitCancelled()
            return draft
        with patch.object(strategy, "design", side_effect=stop_after_design), patch.object(
                DesignedWaterPlacementPreparer, "prepare", side_effect=AssertionError("geometry after shutdown")):
            with self.assertRaises(PlanWaitCancelled):
                prepare_designed_water(**args)

    def test_cancellation_and_programming_errors_propagate_without_success(self):
        case = self.case()
        args = self.arguments(case)
        args["control"].raise_if_shutdown.side_effect = PlanWaitCancelled()
        with self.assertRaises(PlanWaitCancelled):
            prepare_designed_water(**args)
        args["prepare_input"].assert_not_called()
        for error in (RuntimeError("caller failed"), PlanWaitCancelled()):
            args = self.arguments(case)
            args["prepare_input"].side_effect = error
            with self.assertRaises(type(error)):
                prepare_designed_water(**args)
