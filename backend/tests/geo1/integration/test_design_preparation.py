"""Joint J05–J07 execution, without activating legacy water transports."""

from unittest import TestCase
from unittest.mock import Mock, patch

from app.application.planning.service.planningService import PlanBuildFailure, PlanWaitCancelled
from app.application.worldData.generators.terrain.designedWater.preparation.designPreparation import prepare_designed_water
from app.application.worldData.generators.terrain.designedWater.strategies.strategyFactory import DesignedWaterStrategyFactory
from app.application.worldData.placement.lifecycle.session import PlacementSession
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.common import DependencyRelation, PlacementPhase
from app.dataModel.placement.intent import PlacementDependency, PlacementIntent
from app.dataModel.placement.lifecycle.header import PlacementHeader
from app.dataModel.placement.result import DisabledPlacement, ResolvedPlacementV2, UnresolvedPlacementV2
from app.dataModel.policy.policyEnums import PolicyState
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from tests.geo1.contracts.strategies import test_dispatch_budget as joins
from tests.geo1.contracts import test_placement_lifecycle as lifecycle
from tests.geo1.coverage import test_budget as coverage
from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionPlan, TerrainRegionsSnapshot
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageRequest
from app.dataModel.terrain.designedWater.geometry.authoredGeometry import AuthoredWaterGeometry
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace


class DesignPreparationTests(TestCase):
    def case(self, kind=Strategy.AUTHORED_REGION):
        owner, value, design, intent, admission = joins.PreparedWaterAdmissionTests().case(kind)
        if kind is not Strategy.AUTHORED_REGION:
            # The leaf fixture deliberately permits arbitrary ready allocations.
            # Here J04 owns the request: 0.5 of this fixture's 16 fine cells = 8.
            value = type(value).model_validate(value.model_copy(update={
                "budget": value.budget.model_copy(update={"requested_fine2": 8})}))
        return owner, value, design, intent, admission

    def arguments(self, case, *, competitors=()):
        _, value, _, intent, admission = case
        batch = PlacementBatchV2(world_uid="world", snapshot_uid="pre-relief",
            snapshot_revision=value.pre_hydrology_ref.output_fingerprint, phase=PlacementPhase.PRE_RELIEF,
            topology=value.topology, objects=(admission, *competitors), accepted=())
        requests = () if value.strategy is Strategy.AUTHORED_REGION else (BodyCoverageRequest(
            source_uid=value.metadata.source_uid, generation_region_uid=value.region.region_uid,
            generation_area_fine2=value.region.generation_area_fine2, target_fraction=value.context.water_fraction),)
        regions = TerrainRegionPlan(snapshot=TerrainRegionsSnapshot(world_uid="world", snapshot_uid="pre-relief",
            world_region=value.region, regions=()), coverages=(value.region_coverage,))
        return dict(batch=batch, water_intents=(intent,), pre_hydrology=value.pre_hydrology,
            regions=regions, world_context=coverage.context(value.context.water_fraction),
            coverage_requests=requests,
            authored_geometry=(value.geometry,) if value.strategy is Strategy.AUTHORED_REGION else (),
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
                budget, preparations, result = prepare_designed_water(**args)
                design.assert_called_once()
                args["prepare_input"].assert_called_once_with(case[4], budget)
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
            budget, preparations, result = prepare_designed_water(**args)
        outcomes = {o.identity.region_uid: o for o in result.results}
        self.assertIsInstance(outcomes["competitor"], ResolvedPlacementV2)
        self.assertIsInstance(outcomes[case[3].identity.region_uid], UnresolvedPlacementV2)
        self.assertEqual(preparations, (case[2],))  # retain loser's floor/metadata/notices
        args["batch"] = args["batch"].model_copy(update={"objects": tuple(reversed(args["batch"].objects))})
        self.assertEqual(prepare_designed_water(**args), (budget, preparations, result))

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
            args["authored_geometry"] = ()
            budget, preparations, result = prepare_designed_water(**args)
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
        def ready(obj, budget):
            events.append("water")
            self.assertEqual(obj.decision, original[4].decision)
            return original[1]
        args.update(prepare_input=ready, reevaluate_support=resume)
        budget, preparations, result = prepare_designed_water(**args)
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
            budget, preparations, result = prepare_designed_water(**args)
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
        budget, preparations, result = prepare_designed_water(**args)
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
                budget, preparations, result = prepare_designed_water(**args)
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
        args["authored_geometry"] = tuple(case[1].geometry for case in renamed)
        inputs = {case[1].metadata.source_uid: case[1] for case in renamed}
        args["prepare_input"] = Mock(side_effect=lambda obj, budget: inputs[obj.header.identity.source_uid])
        budget, preparations, result = prepare_designed_water(**args)
        self.assertEqual({p.metadata.source_uid for p in preparations}, set(inputs))
        self.assertEqual(args["prepare_input"].call_count, 2)
        self.assertEqual(sum(isinstance(o, ResolvedPlacementV2) for o in result.results), 1)
        self.assertEqual(sum(isinstance(o, UnresolvedPlacementV2) for o in result.results), 1)
        args["prepare_competitor"].assert_not_called()

    def test_cycle_is_settled_without_input_or_geometry(self):
        case = self.dependent_case(self.case())
        support = lifecycle.member("support", targets=(case[3].identity.region_uid,))
        args = self.arguments(case, competitors=(support,))
        budget, preparations, result = prepare_designed_water(**args)
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

    def rename(self, case, uid):
        owner, value, design, intent, admission = case
        source = value.source.model_copy(update={"value": value.source.value.model_copy(update={"source_uid": uid})})
        value = type(value).model_validate(value.model_copy(update={"source": source,
            "metadata": value.metadata.model_copy(update={"source_uid": uid}),
            "budget": value.budget.model_copy(update={"source_uid": uid})}))
        intent = intent.model_copy(update={"identity": intent.identity.model_copy(update={"source_uid": uid, "region_uid": uid})})
        return owner, value, design, intent, admission.model_copy(update={"header": PlacementHeader.from_intent(intent)})

    def test_one_budget_precedes_all_inputs_and_p2_never_redistributes_losing_allocations(self):
        from app.application.worldData.generators.terrain.designedWater.coverage.waterCoverageBudgetPolicy import WaterCoverageBudgetPolicy
        cases = [self.rename(self.case(Strategy.CONTINENTAL_NOISE), uid) for uid in ("a", "b")]
        competitor = lifecycle.member("reserved", priority=20)
        args = self.arguments(cases[0], competitors=(cases[1][4], competitor))
        args["water_intents"] = tuple(c[3] for c in cases)
        args["coverage_requests"] += (args["coverage_requests"][0].model_copy(update={"source_uid": "b"}),)
        values = {c[1].metadata.source_uid: c[1] for c in cases}
        events = []
        def ready(obj, budget):
            events.append((obj.header.identity.source_uid, budget))
            value = values[obj.header.identity.source_uid]
            allocation = next(a for a in budget.allocations if a.source_uid == value.metadata.source_uid)
            return type(value).model_validate(value.model_copy(update={"budget": allocation}))
        args["prepare_input"] = ready
        args["prepare_competitor"] = lambda obj: lifecycle.prepared(obj, cells=((0, 0), (1, 0), (0, 1), (1, 1)))
        original = WaterCoverageBudgetPolicy.calculate
        with patch.object(WaterCoverageBudgetPolicy, "calculate", autospec=True, side_effect=original) as calculate:
            budget, designs, result = prepare_designed_water(**args)
        calculate.assert_called_once()
        self.assertEqual([a.allocated_fine2 for a in budget.allocations], [4, 4])
        self.assertTrue(all(seen is budget for _, seen in events))
        self.assertEqual(len(designs), 2)
        self.assertEqual(sum(isinstance(o, ResolvedPlacementV2) for o in result.results), 1)
        self.assertEqual(sum(isinstance(o, UnresolvedPlacementV2) for o in result.results), 2)
        args["batch"] = args["batch"].model_copy(update={"objects": tuple(reversed(args["batch"].objects))})
        args["water_intents"] = tuple(reversed(args["water_intents"]))
        args["coverage_requests"] = tuple(reversed(args["coverage_requests"]))
        self.assertEqual(prepare_designed_water(**args), (budget, designs, result))

    def test_foreign_allocation_or_body_fraction_is_rejected_before_design(self):
        case = self.case(Strategy.PLATE)
        for update in ({"budget": case[1].budget.model_copy(update={"allocated_fine2": 4})},
                {"context": case[1].context.model_copy(update={"water_fraction": 0.25})}):
            args = self.arguments(case)
            args["prepare_input"].return_value = type(case[1]).model_validate(case[1].model_copy(update=update))
            with patch.object(args["strategies"], "get", side_effect=AssertionError("unbound budget reached design")):
                budget, designs, result = prepare_designed_water(**args)
            self.assertEqual(budget.allocations[0].allocated_fine2, 8)
            self.assertEqual(designs, ())
            self.assertIsInstance(result.results[0], UnresolvedPlacementV2)

    def test_invalid_request_set_or_terrain_area_fails_before_input_or_budget(self):
        from app.application.worldData.generators.terrain.designedWater.coverage.waterCoverageBudgetPolicy import WaterCoverageBudgetPolicy
        case = self.case(Strategy.PLATE)
        request = self.arguments(case)["coverage_requests"][0]
        for requests in ((), (request.model_copy(update={"source_uid": "foreign"}),),
                (request.model_copy(update={"generation_area_fine2": 8}),),
                (request.model_copy(update={"generation_region_uid": "missing"}),)):
            args = self.arguments(case)
            args["coverage_requests"] = requests
            with patch.object(WaterCoverageBudgetPolicy, "calculate", side_effect=AssertionError("invalid universe")):
                with self.assertRaises(PlanBuildFailure):
                    prepare_designed_water(**args)
            args["prepare_input"].assert_not_called()
        args = self.arguments(case)
        args["coverage_requests"] = (request, request)
        with self.assertRaises(ValueError):
            prepare_designed_water(**args)
        args["prepare_input"].assert_not_called()

    def test_authored_and_disabled_sources_cannot_reserve_procedural_quota(self):
        case = self.case()
        args = self.arguments(case)
        args["coverage_requests"] = (BodyCoverageRequest(source_uid=case[1].metadata.source_uid,
            generation_region_uid=case[1].region.region_uid,
            generation_area_fine2=case[1].region.generation_area_fine2, target_fraction=0.5),)
        with self.assertRaises(PlanBuildFailure):
            prepare_designed_water(**args)
        args["prepare_input"].assert_not_called()
        case = self.case(Strategy.PLATE)
        from tests.geo1.placement_policy.fixtures import bind, execute
        obj = case[4].model_copy(update={"decision": execute(bind(source=case[1].source,
            enabled=False, strategy=case[1].strategy))})
        args = self.arguments(case)
        args["batch"] = args["batch"].model_copy(update={"objects": (obj,)})
        with self.assertRaises(PlanBuildFailure):
            prepare_designed_water(**args)
        args["coverage_requests"] = ()
        budget, designs, result = prepare_designed_water(**args)
        self.assertEqual(budget.allocations, ())
        self.assertEqual(designs, ())
        self.assertIsInstance(result.results[0], DisabledPlacement)
        args["prepare_input"].assert_not_called()

    def test_zero_target_reaches_existing_empty_geometry_failure_without_fake_water(self):
        case = self.case(Strategy.CONTINENTAL_NOISE)
        for fraction in (0.0,):
            args = self.arguments(case)
            args.update(world_context=coverage.context(fraction))
            def ready(obj, budget):
                return type(case[1]).model_validate(case[1].model_copy(update={"budget": budget.allocations[0]}))
            args["prepare_input"] = ready
            budget, designs, result = prepare_designed_water(**args)
            self.assertEqual(budget.allocations[0].allocated_fine2, 0)
            self.assertEqual(designs, ())
            self.assertIsInstance(result.results[0], UnresolvedPlacementV2)
            self.assertIn("EMPTY_GENERATION_TARGET", result.results[0].diagnostics[0].detail)

    def test_region_snapshot_identity_and_fixed_world_extent_are_required_before_input(self):
        case = self.case(Strategy.PLATE)
        base = self.arguments(case)["regions"]
        for update in ({"world_uid": "foreign"}, {"snapshot_uid": "stale"},
                {"world_region": None, "regions": (base.snapshot.world_region,)}):
            args = self.arguments(case)
            args["regions"] = base.model_copy(update={"snapshot": base.snapshot.model_copy(update=update)})
            with self.assertRaises(PlanBuildFailure):
                prepare_designed_water(**args)
            args["prepare_input"].assert_not_called()

    def test_authored_only_without_declared_world_extent_has_no_global_budget(self):
        from app.application.worldData.generators.terrain.designedWater.coverage.waterCoverageBudgetPolicy import WaterCoverageBudgetPolicy
        case = self.case()
        args = self.arguments(case)
        plan = args["regions"]
        args["regions"] = plan.model_copy(update={"snapshot": plan.snapshot.model_copy(update={
            "world_region": None, "regions": (case[1].region,)})})
        with patch.object(WaterCoverageBudgetPolicy, "calculate", side_effect=AssertionError("invented global metric")):
            budget, designs, result = prepare_designed_water(**args)
        self.assertIsNone(budget)
        self.assertEqual(designs, (case[2],))
        self.assertIsInstance(result.results[0], ResolvedPlacementV2)
        args["prepare_input"].assert_called_once_with(case[4], None)

    def test_waiting_procedural_source_keeps_one_allocation_through_support_resume(self):
        original = self.case(Strategy.PLATE)
        case = self.dependent_case(original, waiting=True)
        args = self.arguments(case, competitors=(lifecycle.member("support", priority=10),))
        args["prepare_competitor"] = lambda obj: lifecycle.prepared(obj, cells=((0, 0),))
        args["reevaluate_support"] = Mock(return_value=original[4].decision)
        budget, designs, result = prepare_designed_water(**args)
        self.assertEqual(budget.allocations, (original[1].budget,))
        self.assertEqual(len(designs), 1)
        args["reevaluate_support"].assert_called_once()
        args["prepare_input"].assert_called_once_with(case[4].model_copy(update={
            "decision": original[4].decision}), budget)

    def test_ready_authored_region_must_exist_in_captured_snapshot(self):
        case = self.case()
        args = self.arguments(case)
        value = case[1]
        args["prepare_input"].return_value = type(value).model_validate(value.model_copy(update={
            "region": value.region.model_copy(update={"region_uid": "foreign"}),
            "region_coverage": value.region_coverage.model_copy(update={"region_uid": "foreign"}),
            "budget": value.budget.model_copy(update={"generation_region_uid": "foreign"})}))
        with patch.object(args["strategies"], "get", side_effect=AssertionError("foreign region reached design")):
            budget, designs, result = prepare_designed_water(**args)
        self.assertEqual(designs, ())
        self.assertIsInstance(result.results[0], UnresolvedPlacementV2)

    def test_noncanonical_fine_coverage_fails_before_budget_or_source_input(self):
        args = self.arguments(self.case(Strategy.PLATE))
        plan = args["regions"]
        original = plan.coverages[0]
        shifted = original.model_copy(update={"spans": tuple(span.model_copy(update={
            "x0": span.x0 + 100, "x1": span.x1 + 100}) for span in original.spans)})
        args["regions"] = plan.model_copy(update={"coverages": (shifted,)})
        with self.assertRaises(PlanBuildFailure):
            prepare_designed_water(**args)
        args["prepare_input"].assert_not_called()

    def add_captured_authored(self, args, uid, cells, *, fine=False):
        sample = self.case()
        obj = lifecycle.member(uid, chosen=sample[4].decision)
        header = obj.header
        intent = PlacementIntent(identity=header.identity, mode=header.mode, shape=None,
            dependencies=header.dependencies, permitted_overlaps=header.permitted_overlaps, separations=header.separations)
        geometry = AuthoredWaterGeometry.model_validate(sample[1].geometry.model_copy(update={
            "source_uid": header.identity.source_uid, "pre_hydrology_ref": args["pre_hydrology"].ref,
            "coordinate_space": CoordinateSpace.WORLD_FINE_GRID if fine else CoordinateSpace.WORLD_SURFACE_GRID,
            "footprints": (frozenset(cells),)}))
        args["batch"] = args["batch"].model_copy(update={"objects": (*args["batch"].objects, obj)})
        args["water_intents"] += (intent,)
        args["authored_geometry"] += (geometry,)
        return geometry

    def test_authored_overlap_is_measured_once_and_failed_sources_do_not_redistribute(self):
        case = self.case(Strategy.CONTINENTAL_NOISE)
        args = self.arguments(case)
        self.add_captured_authored(args, "a", {(0, 0), (1, 0)})
        self.add_captured_authored(args, "b", {(1, 0), (1, 1)})
        args["world_context"] = coverage.context(1.0)
        def ready(obj, budget):
            if obj.header.identity.source_uid != case[1].metadata.source_uid:
                raise PlanBuildFailure((FieldPathError(("authored",), "source preparation failed", code="authored_failure"),))
            return type(case[1]).model_validate(case[1].model_copy(update={"budget": budget.allocations[0]}))
        args["prepare_input"] = ready
        budget, designs, result = prepare_designed_water(**args)
        self.assertEqual((budget.area_fine2, budget.target_fine2, budget.authored_union_fine2, budget.residual_fine2), (16, 16, 12, 4))
        self.assertEqual(budget.allocations[0].allocated_fine2, 4)
        self.assertEqual(len(designs), 1)
        self.assertEqual(sum(isinstance(o, ResolvedPlacementV2) for o in result.results), 1)
        args["authored_geometry"] = tuple(reversed(args["authored_geometry"]))
        args["batch"] = args["batch"].model_copy(update={"objects": tuple(reversed(args["batch"].objects))})
        self.assertEqual(prepare_designed_water(**args), (budget, designs, result))

    def test_available_area_is_union_of_requested_regions_minus_authored_geometry(self):
        from tests.geo1.regions.test_coverage import coverage as make_coverage
        from app.dataModel.terrain.regions.terrainRegionExtent import TerrainRegionExtent
        case = self.case(Strategy.PLATE)
        second = self.rename(case, "second")
        args = self.arguments(case, competitors=(second[4],))
        args["water_intents"] += (second[3],)
        self.add_captured_authored(args, "authored", {(0, 0)})
        auto = make_coverage({(x, y) for x in range(4) for y in range(2)}, "auto")
        plan = args["regions"]
        args["regions"] = plan.model_copy(update={"snapshot": plan.snapshot.model_copy(update={
            "regions": (TerrainRegionExtent(region_uid="auto", generation_area_fine2=8),)}),
            "coverages": (*plan.coverages, auto)})
        args["coverage_requests"] = tuple(BodyCoverageRequest(source_uid=c[1].metadata.source_uid,
            generation_region_uid="auto", generation_area_fine2=8, target_fraction=1.0) for c in (case, second))
        args["world_context"] = coverage.context(1.0)
        args["prepare_input"].side_effect = PlanBuildFailure((FieldPathError(("source",), "stop after budget", code="stop"),))
        budget, designs, result = prepare_designed_water(**args)
        self.assertEqual((budget.authored_union_fine2, budget.residual_fine2), (4, 12))
        self.assertEqual([a.allocated_fine2 for a in budget.allocations], [2, 2])
        self.assertEqual(designs, ())

    def test_native_fine_geometry_is_not_scaled_a_second_time(self):
        case = self.case(Strategy.PLATE)
        args = self.arguments(case)
        self.add_captured_authored(args, "fine", {(0, 0), (1, 0), (3, 3)}, fine=True)
        args["prepare_input"].side_effect = PlanBuildFailure((FieldPathError(("source",), "stop after budget", code="stop"),))
        budget, designs, result = prepare_designed_water(**args)
        self.assertEqual(budget.authored_union_fine2, 3)

    def test_terminal_sources_supply_no_geometry_and_are_not_measured(self):
        from app.application.worldData.generators.terrain.regions.coverageMeasure import RegionCoverageMeasure
        from tests.geo1.placement_policy.fixtures import bind, execute
        case = self.case()
        args = self.arguments(case)
        off = case[4].model_copy(update={"decision": execute(bind(source=case[1].source, enabled=False, strategy=case[1].strategy))})
        args["batch"] = args["batch"].model_copy(update={"objects": (off,)})
        with self.assertRaises(PlanBuildFailure):
            prepare_designed_water(**args)
        args["authored_geometry"] = ()
        with patch.object(RegionCoverageMeasure, "from_cells", side_effect=AssertionError("disabled geometry measured")):
            budget, designs, result = prepare_designed_water(**args)
        self.assertEqual(budget.authored_union_fine2, 0)
        self.assertIsInstance(result.results[0], DisabledPlacement)
        args["prepare_input"].assert_not_called()

    def test_stale_duplicate_foreign_or_noncanonical_authored_geometry_fails_before_input(self):
        case = self.case()
        geometry = case[1].geometry
        variants = ((geometry, geometry), (geometry.model_copy(update={"source_uid": "foreign"}),),
            (geometry.model_copy(update={"pre_hydrology_ref": geometry.pre_hydrology_ref.model_copy(update={"output_fingerprint": b"s"*32})}),),
            (geometry.model_copy(update={"footprints": (frozenset({(10000, 10000)}),)}),))
        for geometries in variants:
            args = self.arguments(case)
            args["authored_geometry"] = geometries
            with self.assertRaises(PlanBuildFailure):
                prepare_designed_water(**args)
            args["prepare_input"].assert_not_called()

    def test_authored_ready_input_reuses_exact_geometry_that_was_measured(self):
        case = self.case()
        args = self.arguments(case)
        different = case[1].geometry.model_copy(update={"notices": (FieldPathError(("source",), "changed", code="changed"),)})
        args["prepare_input"].return_value = type(case[1]).model_validate(case[1].model_copy(update={"geometry": different}))
        with patch.object(args["strategies"], "get", side_effect=AssertionError("geometry changed after budget")):
            budget, designs, result = prepare_designed_water(**args)
        self.assertEqual(designs, ())
        self.assertIsInstance(result.results[0], UnresolvedPlacementV2)

    def test_planned_authored_union_above_target_is_not_clipped_or_negative(self):
        case = self.case(Strategy.PLATE)
        args = self.arguments(case)
        geometry = self.add_captured_authored(args, "large", {(0, 0), (1, 0), (0, 1)})
        before = geometry.model_dump()
        def ready(obj, budget):
            if obj.header.identity.source_uid != case[1].metadata.source_uid:
                raise PlanBuildFailure((FieldPathError(("source",), "failed authored source", code="authored_failure"),))
            return type(case[1]).model_validate(case[1].model_copy(update={"budget": budget.allocations[0]}))
        args["prepare_input"] = ready
        budget, designs, result = prepare_designed_water(**args)
        self.assertEqual((budget.target_fine2, budget.authored_union_fine2, budget.residual_fine2), (8, 12, 0))
        self.assertEqual(budget.allocations[0].allocated_fine2, 0)
        self.assertEqual(designs, ())
        self.assertTrue(all(isinstance(o, UnresolvedPlacementV2) for o in result.results))
        self.assertEqual(geometry.model_dump(), before)

    def test_initial_common_dependency_failure_is_excluded_before_measurement_and_allocation(self):
        from app.application.worldData.generators.terrain.regions.coverageMeasure import RegionCoverageMeasure
        for kind in (Strategy.AUTHORED_REGION, Strategy.PLATE):
            args = self.arguments(self.dependent_case(self.case(kind), target="missing"))
            with patch.object(RegionCoverageMeasure, "from_cells", side_effect=AssertionError("terminal geometry measured")):
                budget, designs, result = prepare_designed_water(**args)
            self.assertEqual(budget.authored_union_fine2, 0)
            self.assertEqual(budget.allocations, ())
            self.assertEqual(designs, ())
            self.assertIsInstance(result.results[0], UnresolvedPlacementV2)
            args["prepare_input"].assert_not_called()
            if kind is Strategy.AUTHORED_REGION:
                args["authored_geometry"] = ()
                self.assertEqual(prepare_designed_water(**args), (budget, designs, result))

    def test_pending_competitor_with_same_source_uid_does_not_restore_terminal_water_request(self):
        case = self.dependent_case(self.case(Strategy.PLATE), target="missing")
        other = lifecycle.member("other")
        other = other.model_copy(update={"header": other.header.model_copy(update={
            "identity": other.header.identity.model_copy(update={"source_uid": case[1].metadata.source_uid})})})
        args = self.arguments(case, competitors=(other,))
        args["prepare_competitor"] = lambda obj: lifecycle.prepared(obj, cells=((0, 0),))
        budget, designs, result = prepare_designed_water(**args)
        self.assertEqual(budget.allocations, ())
        self.assertEqual(designs, ())
        self.assertEqual(sum(isinstance(o, ResolvedPlacementV2) for o in result.results), 1)
        args["prepare_input"].assert_not_called()
