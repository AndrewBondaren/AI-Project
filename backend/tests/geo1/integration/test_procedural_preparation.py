"""Native source settings through real cascade/policy/design/common placement."""

from unittest import TestCase
from unittest.mock import Mock, patch

from app.application.planning.service.planningService import PlanBuildFailure, PlanWaitCancelled
from app.application.worldData.generators.terrain.designedWater.preparation.proceduralDesignPreparation import prepare_procedural_designed_water
from app.application.worldData.generators.terrain.designedWater.preparation.proceduralWaterSourceAdapter import ProceduralWaterSourceAdapter
from app.application.worldData.generators.terrain.designedWater.strategies.strategyFactory import DesignedWaterStrategyFactory
from app.application.worldData.generators.hydrology.sources.waterSourceMetadataFactory import WaterSourceMetadataFactory
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationScope as Scope
from app.dataModel.hydrology.generation.waterGenerationSettings import WorldWaterGenerationSettings, CategoryWaterGenerationSettings, BodyWaterGenerationSettings
from app.dataModel.hydrology.generation.waterGenerationDefaults import WaterGenerationDefaults
from app.dataModel.hydrology.lakes import HydrologyLakesPolicy
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.common import PlacementMode, PlacementPhase, DependencyRelation
from app.dataModel.placement.intent import PlacementIdentity, PlacementIntent, PlacementDependency
from app.dataModel.placement.result import DisabledPlacement, ResolvedPlacementV2, UnresolvedPlacementV2
from app.dataModel.terrain.designedWater.settings.continentalNoisePolicy import ContinentalNoisePolicy
from app.dataModel.terrain.designedWater.settings.fieldCompositionPolicy import FieldCompositionPolicy
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
from app.dataModel.terrain.designedWater.settings.plateGenerationPolicy import PlateGenerationPolicy
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.terrain.planning.inputs.geoWaterPlacementInput import GeoWaterPlacementInput
from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionPlan, TerrainRegionsSnapshot
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from tests.geo1.preparation.fixtures import procedural_case
from tests.geo1.contracts import test_placement_lifecycle as lifecycle


class ProceduralPreparationTests(TestCase):
    def case(self, strategy=Strategy.CONTINENTAL_NOISE):
        value, _ = procedural_case(strategy=strategy)
        inputs = GeoWaterPlacementInput(enabled=True, resolution_mode=ResolutionMode.VALIDATE_ONLY,
            declared_world_bounds=value.topology.bounds, default_water_level=0,
            generation=WorldWaterGenerationSettings(autoresolve=True, strategy=strategy, water_fraction=0.5),
            defaults=WaterGenerationDefaults(), sea_generation=CategoryWaterGenerationSettings(),
            ocean_generation=CategoryWaterGenerationSettings(), lake_generation=CategoryWaterGenerationSettings(),
            seas=HydrologySeasPolicy(placement_specificity=3), lakes=HydrologyLakesPolicy(placement_specificity=3),
            sources=(value.source,), anchors=(), topology=value.topology, grid=value.grid, z_min=-20, z_max=30,
            liquid_keys=frozenset({"water"}), noise_policy=ContinentalNoisePolicy(), plate_policy=PlateGenerationPolicy(),
            composition_policy=FieldCompositionPolicy(), selection_policy=WaterFieldSelectionPolicy())
        intent = PlacementIntent(identity=PlacementIdentity(world_uid="world", source_uid="source", region_uid="water"),
            mode=PlacementMode.ABSOLUTE, shape=None, dependencies=(), permitted_overlaps=(), separations=())
        return dict(inputs=inputs, batch=PlacementBatchV2(world_uid="world", snapshot_uid="pre-relief",
            snapshot_revision=value.pre_hydrology_ref.output_fingerprint, phase=PlacementPhase.PRE_RELIEF,
            topology=value.topology, objects=(), accepted=()), water_intents=(intent,), pre_hydrology=value.pre_hydrology,
            regions=TerrainRegionPlan(snapshot=TerrainRegionsSnapshot(world_uid="world", snapshot_uid="pre-relief",
                world_region=value.region, regions=()), coverages=(value.region_coverage,)), seed_root=value.seed_root,
            prepare_competitor=Mock(side_effect=AssertionError("unexpected competitor")),
            strategies=DesignedWaterStrategyFactory.builtins(), control=Mock())

    def run_case(self, args):
        original = ProceduralWaterSourceAdapter.prepare_source
        with patch.object(ProceduralWaterSourceAdapter, "prepare_source", autospec=True, side_effect=original) as adapter:
            result = prepare_procedural_designed_water(**args)
        return result, adapter

    def test_three_strategies_are_prepared_from_owners_without_caller_inputs_or_requests(self):
        for strategy in (Strategy.CONTINENTAL_NOISE, Strategy.PLATE, Strategy.PLATE_NOISE):
            args = self.case(strategy)
            (budget, designs, result), adapter = self.run_case(args)
            self.assertEqual(budget.allocations[0].requested_fine2, 8)
            self.assertEqual(budget.allocations[0].allocated_fine2, 8)
            self.assertEqual(len(designs), 1)
            self.assertIsInstance(result.results[0], ResolvedPlacementV2)
            self.assertEqual(designs[0].floor_profile.recipe.strategy, strategy)
            adapter.assert_called_once()
            shared = adapter.call_args.args[1]
            self.assertTrue(shared.context.autoresolve)
            self.assertEqual(shared.context.level, Scope.WATER_BODY)
            self.assertEqual(shared.budget, budget.allocations[0])

    def test_body_overrides_category_and_world_and_retains_provenance(self):
        args = self.case()
        source = args["inputs"].sources[0]
        source = source.model_copy(update={"value": source.value.model_copy(update={"generation": BodyWaterGenerationSettings(
            autoresolve=True, strategy=Strategy.PLATE, water_fraction=0.25)})})
        args["inputs"] = args["inputs"].model_copy(update={"sources": (source,),
            "sea_generation": CategoryWaterGenerationSettings(autoresolve=False, strategy=Strategy.PLATE_NOISE)})
        (budget, designs, result), adapter = self.run_case(args)
        context = adapter.call_args.args[1].context
        self.assertEqual(budget.allocations[0].requested_fine2, 4)
        self.assertEqual(context.strategy, Strategy.PLATE)
        self.assertTrue(context.autoresolve)
        self.assertEqual(dict(context.provenance)["water_fraction"], (Scope.WATER_BODY, "BodyWaterGenerationSettings.water_fraction"))
        self.assertEqual(designs[0].floor_profile.recipe.strategy, Strategy.PLATE)

    def test_false_none_and_disabled_gates_never_execute_metadata_or_fields(self):
        for change in ({"generation": WorldWaterGenerationSettings()}, {"enabled": False},
                {"sea_generation": CategoryWaterGenerationSettings(autoresolve=False)},
                {"seas": HydrologySeasPolicy(enabled=False, placement_specificity=3)}):
            args = self.case()
            args["inputs"] = args["inputs"].model_copy(update=change)
            with patch.object(WaterSourceMetadataFactory, "build", side_effect=AssertionError("disabled metadata")), \
                 patch.object(args["strategies"], "get", side_effect=AssertionError("disabled field")):
                budget, designs, result = prepare_procedural_designed_water(**args)
            self.assertEqual(budget.allocations, ())
            self.assertEqual(designs, ())
            self.assertIsInstance(result.results[0], DisabledPlacement)

    def test_body_false_is_a_normal_policy_disable_with_domain_reason(self):
        from app.dataModel.hydrology.policy.hydrologyGenerationDecision import WaterPolicyReason
        args = self.case()
        source = args["inputs"].sources[0]
        source = source.model_copy(update={"value": source.value.model_copy(update={
            "generation": BodyWaterGenerationSettings(autoresolve=False)})})
        args["inputs"] = args["inputs"].model_copy(update={"sources": (source,)})
        (budget, designs, result), adapter = self.run_case(args)
        self.assertIsInstance(result.results[0], DisabledPlacement)
        self.assertIn(WaterPolicyReason.DECLARED_ONLY, [r.domain_reason for r in result.results[0].decision.reasons])
        adapter.assert_not_called()

    def test_category_selection_uses_ocean_and_lake_channels(self):
        for kind, settings_field in ((BasinKind.OCEAN, "ocean_generation"), (BasinKind.LAKE, "lake_generation")):
            args = self.case()
            source = args["inputs"].sources[0]
            source = source.model_copy(update={"value": source.value.model_copy(update={"kind": kind})})
            args["inputs"] = args["inputs"].model_copy(update={"sources": (source,), settings_field:
                CategoryWaterGenerationSettings(strategy=Strategy.PLATE, water_fraction=0.25)})
            (budget, designs, result), adapter = self.run_case(args)
            self.assertEqual(designs[0].metadata.body_kind, kind)
            self.assertEqual(designs[0].floor_profile.recipe.strategy, Strategy.PLATE)
            self.assertEqual(budget.allocations[0].requested_fine2, 4)
            self.assertEqual(dict(adapter.call_args.args[1].context.provenance)["strategy"], (Scope.CATEGORY, "CategoryWaterGenerationSettings.strategy"))

    def test_explicit_zero_priority_disables_and_none_uses_captured_category(self):
        for priority, expected in ((0, DisabledPlacement), (None, ResolvedPlacementV2)):
            args = self.case()
            source = args["inputs"].sources[0]
            source = source.model_copy(update={"value": source.value.model_copy(update={"placement_specificity": priority})})
            args["inputs"] = args["inputs"].model_copy(update={"sources": (source,), "seas": HydrologySeasPolicy(placement_specificity=3)})
            (budget, designs, result), adapter = self.run_case(args)
            self.assertIsInstance(result.results[0], expected)
            self.assertEqual(adapter.call_count, 0 if priority == 0 else 1)

    def test_competitor_and_native_water_use_the_same_spatial_batch(self):
        args = self.case()
        competitor = lifecycle.member("competitor", priority=10)
        args["batch"] = args["batch"].model_copy(update={"objects": (competitor,)})
        args["prepare_competitor"] = lambda obj: lifecycle.prepared(obj, cells=((0, 0), (1, 0), (0, 1), (1, 1)))
        budget, designs, result = prepare_procedural_designed_water(**args)
        outcomes = {o.identity.region_uid: o for o in result.results}
        self.assertIsInstance(outcomes["competitor"], ResolvedPlacementV2)
        self.assertIsInstance(outcomes["water"], UnresolvedPlacementV2)
        self.assertEqual(budget.allocations[0].allocated_fine2, 8)
        self.assertEqual(len(designs), 1)

    def test_missing_dependency_is_terminal_before_native_input_preparation(self):
        args = self.case()
        args["water_intents"] = (args["water_intents"][0].model_copy(update={"dependencies": (
            PlacementDependency(target_uid="missing", relation=DependencyRelation.RESOLVED),)}),)
        (budget, designs, result), adapter = self.run_case(args)
        self.assertEqual(budget.allocations, ())
        self.assertIsInstance(result.results[0], UnresolvedPlacementV2)
        adapter.assert_not_called()

    def test_no_sources_never_synthesizes_implicit_ocean(self):
        args = self.case()
        args["inputs"] = args["inputs"].model_copy(update={"sources": ()})
        args["water_intents"] = ()
        budget, designs, result = prepare_procedural_designed_water(**args)
        self.assertEqual((budget.allocations, designs, result.results), ((), (), ()))

    def test_authored_wrapper_or_missing_intent_is_rejected_before_design(self):
        from tests.geo1.contracts.strategies.fixtures import inputs
        args = self.case()
        args["inputs"] = args["inputs"].model_copy(update={"sources": (inputs(Strategy.AUTHORED_REGION).source,)})
        with self.assertRaises(PlanBuildFailure):
            prepare_procedural_designed_water(**args)
        args = self.case()
        args["water_intents"] = ()
        with self.assertRaises(PlanBuildFailure):
            prepare_procedural_designed_water(**args)

    def test_active_source_requires_declared_bounds_region_and_field_strategy(self):
        for change in ({"generation": WorldWaterGenerationSettings(
                autoresolve=True, strategy=Strategy.AUTHORED_REGION)},):
            args = self.case()
            args["inputs"] = args["inputs"].model_copy(update=change)
            with self.assertRaises(PlanBuildFailure):
                prepare_procedural_designed_water(**args)
        args = self.case()
        source = args["inputs"].sources[0]
        source = source.model_copy(update={"value": source.value.model_copy(update={"generation_region_uid": "missing"})})
        args["inputs"] = args["inputs"].model_copy(update={"sources": (source,)})
        with self.assertRaises(PlanBuildFailure):
            prepare_procedural_designed_water(**args)

    def test_captured_inputs_are_immutable_and_full_replay_is_identical(self):
        args = self.case(Strategy.PLATE_NOISE)
        before = {name: args[name].model_dump() for name in ("inputs", "batch", "regions", "pre_hydrology")}
        first = prepare_procedural_designed_water(**args)
        self.assertEqual(prepare_procedural_designed_water(**args), first)
        self.assertEqual({name: args[name].model_dump() for name in before}, before)

    def test_captured_world_extent_presence_cannot_disagree_with_region_snapshot(self):
        args = self.case()
        self.without_world_region(args)
        with self.assertRaises(PlanBuildFailure):
            prepare_procedural_designed_water(**args)

    def test_cancellation_before_capture_never_runs_policy_or_metadata(self):
        args = self.case()
        args["control"].raise_if_shutdown.side_effect = PlanWaitCancelled()
        with patch.object(WaterSourceMetadataFactory, "build", side_effect=AssertionError("cancelled metadata")):
            with self.assertRaises(PlanWaitCancelled):
                prepare_procedural_designed_water(**args)

    def test_sibling_contexts_requests_and_recipes_are_independent_and_order_invariant(self):
        args = self.case()
        template = args["inputs"].sources[0]
        sources, intents = [], []
        for uid, body in (("a", BodyWaterGenerationSettings(water_fraction=0.25, strategy=Strategy.PLATE)),
                ("b", BodyWaterGenerationSettings())):
            sources.append(template.model_copy(update={"value": template.value.model_copy(update={"source_uid": uid,
                "generation": body})}))
            original = args["water_intents"][0]
            intents.append(original.model_copy(update={"identity": original.identity.model_copy(update={
                "source_uid": uid, "region_uid": uid})}))
        args["inputs"] = args["inputs"].model_copy(update={"sources": tuple(sources)})
        args["water_intents"] = tuple(intents)
        first, adapter = self.run_case(args)
        budget, designs, result = first
        self.assertEqual([(a.source_uid, a.requested_fine2) for a in budget.allocations], [("a", 4), ("b", 8)])
        contexts = {call.args[1].metadata.source_uid: call.args[1].context for call in adapter.call_args_list}
        self.assertEqual(contexts["a"].strategy, Strategy.PLATE)
        self.assertEqual(contexts["b"].strategy, Strategy.CONTINENTAL_NOISE)
        self.assertEqual(contexts["b"].water_fraction, 0.5)
        self.assertEqual(len(designs), 2)
        args["inputs"] = args["inputs"].model_copy(update={"sources": tuple(reversed(sources))})
        args["water_intents"] = tuple(reversed(intents))
        self.assertEqual(prepare_procedural_designed_water(**args), first)

    def test_generation_binding_rejects_foreign_nonterminal_or_fallback_decisions(self):
        from app.application.policy.policyResolver import PolicyResolver
        from app.application.worldData.generators.hydrology.policy.hydrologyGenerationBinding import bind_hydrology_generation_policy
        from app.application.worldData.generators.hydrology.policy.hydrologyPlacementBinding import bind_hydrology_placement_policy
        from app.dataModel.hydrology.policy.hydrologyPlacementPolicy import HydrologyPlacementGateInputs, HydrologyPlacementBehaviorInputs, HydrologyPolicySnapshot
        from app.dataModel.policy.policyEnums import PolicyState
        from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
        from tests.geo1.contracts.strategies.fixtures import inputs
        args = self.case()
        scene = args["inputs"]
        binding = bind_hydrology_generation_policy(enabled=True, generation=scene.generation,
            defaults=scene.defaults, category=scene.sea_generation, body=scene.sources[0].value.generation,
            root_path=("hydrology",), context_path=("context",))
        generation = PolicyResolver().resolve(binding.spec, binding.inputs, binding.facts, mode=scene.resolution_mode)
        kwargs = dict(category=scene.seas, gates=HydrologyPlacementGateInputs(world_enabled=True, category_enabled=True),
            behavior=HydrologyPlacementBehaviorInputs(strategy=Strategy.CONTINENTAL_NOISE),
            snapshot=HydrologyPolicySnapshot(world_uid="world", supports=(), hydrology=None, source_mapping=None, mapping_hydrology_ref=None),
            source_path=("source",), category_path=("seas",))
        with self.assertRaises(ValueError):
            bind_hydrology_placement_policy(inputs(Strategy.AUTHORED_REGION).source, **kwargs, generation=generation)
        for update in ({"state": PolicyState.UNRESOLVED, "issues": (FieldPathError(("source",), "missing", code="missing"),)},
                {"state": PolicyState.DISABLED},
                {"state": PolicyState.DISABLED, "issues": (FieldPathError(("source",), "fallback", code="fallback"),)}):
            with self.assertRaises(ValueError):
                bind_hydrology_placement_policy(scene.sources[0], **kwargs, generation=generation.model_copy(update=update))


    def test_missing_bounds_is_unresolved_in_validation_before_field_preparation(self):
        args = self.case()
        args["inputs"] = args["inputs"].model_copy(update={"declared_world_bounds": None})
        self.without_world_region(args)
        with patch.object(WaterSourceMetadataFactory, "build", side_effect=AssertionError("missing extent metadata")), \
             patch.object(args["strategies"], "get", side_effect=AssertionError("missing extent sampling")):
            budget, designs, result = prepare_procedural_designed_water(**args)
        self.assertIsInstance(result.results[0], UnresolvedPlacementV2)
        self.assertTrue(result.results[0].diagnostics)
        self.assertIsNone(budget)
        self.assertEqual(designs, ())

    def test_missing_bounds_runtime_uses_policy_disable_and_existing_logging_sink(self):
        from app.dataModel.policy.policyEnums import PolicyDisableReason
        args = self.case()
        args["inputs"] = args["inputs"].model_copy(update={"declared_world_bounds": None,
            "resolution_mode": ResolutionMode.RUNTIME})
        self.without_world_region(args)
        with patch("app.application.worldData.generators.hydrology.sources.proceduralSourceAdmission.log_issues") as log, \
             patch.object(WaterSourceMetadataFactory, "build", side_effect=AssertionError("fallback metadata")):
            budget, designs, result = prepare_procedural_designed_water(**args)
        self.assertIsInstance(result.results[0], DisabledPlacement)
        self.assertEqual(result.results[0].reason, PolicyDisableReason.ERROR_FALLBACK)
        self.assertTrue(result.results[0].decision.issues)
        log.assert_called_once_with(result.results[0].decision.issues)
        self.assertIsNone(budget)
        self.assertEqual(designs, ())

    def test_zero_priority_does_not_require_unused_extent_or_emit_fallback(self):
        from app.dataModel.policy.policyEnums import PolicyDisableReason
        args = self.case()
        source = args["inputs"].sources[0]
        source = source.model_copy(update={"value": source.value.model_copy(update={"placement_specificity": 0})})
        args["inputs"] = args["inputs"].model_copy(update={"sources": (source,),
            "declared_world_bounds": None, "resolution_mode": ResolutionMode.RUNTIME})
        self.without_world_region(args)
        with patch("app.application.worldData.generators.hydrology.sources.proceduralSourceAdmission.log_issues") as log:
            budget, designs, result = prepare_procedural_designed_water(**args)
        self.assertEqual(result.results[0].reason, PolicyDisableReason.ZERO_PRIORITY)
        self.assertFalse(result.results[0].decision.issues)
        log.assert_not_called()

    def test_category_and_recipe_owners_are_strict_and_use_captured_settings(self):
        from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationCategory as Category
        from app.application.worldData.generators.terrain.designedWater.strategies.procedural.fieldRecipeFactory import WaterFieldRecipeFactory
        self.assertEqual(Category.for_basin_kind(BasinKind.INLAND_SEA), Category.SEA)
        with self.assertRaises(ValueError):
            Category.for_basin_kind("sea")
        args = self.case()
        args["inputs"] = args["inputs"].model_copy(update={
            "noise_policy": ContinentalNoisePolicy(length_fraction=0.37, octaves=2, lacunarity=3.0, persistence=0.7),
            "plate_policy": PlateGenerationPolicy(plate_count=5, blend_length_fraction=0.31),
            "composition_policy": FieldCompositionPolicy(detail_weight=0.63),
        })
        for kind in (Strategy.CONTINENTAL_NOISE, Strategy.PLATE, Strategy.PLATE_NOISE):
            recipe = WaterFieldRecipeFactory().build(kind, args["inputs"], "captured-seed")
            self.assertEqual(recipe.strategy, kind)
            self.assertEqual(recipe.seed_root, "captured-seed")
            if hasattr(recipe, "noise_policy"):
                self.assertEqual(recipe.noise_policy, args["inputs"].noise_policy)
            if hasattr(recipe, "plate_policy"):
                self.assertEqual(recipe.plate_policy, args["inputs"].plate_policy)
            if hasattr(recipe, "composition_policy"):
                self.assertEqual(recipe.composition_policy, args["inputs"].composition_policy)
        for kind in (Strategy.AUTHORED_REGION, "plate", None):
            with self.assertRaises(PlanBuildFailure):
                WaterFieldRecipeFactory().build(kind, args["inputs"], "captured-seed")

    def test_admission_provenance_names_captured_category_fields(self):
        from app.application.worldData.generators.hydrology.sources.proceduralSourceAdmission import ProceduralSourceAdmissionJob
        for kind, expected_path in ((BasinKind.SEA, ("seas", "placement_specificity")),
                                    (BasinKind.OCEAN, ("seas", "placement_specificity")),
                                    (BasinKind.LAKE, ("lakes", "placement_specificity"))):
            args = self.case()
            source = args["inputs"].sources[0]
            source = source.model_copy(update={"value": source.value.model_copy(update={"kind": kind})})
            args["inputs"] = args["inputs"].model_copy(update={"sources": (source,)})
            bindings = ProceduralSourceAdmissionJob().resolve(args["inputs"], args["batch"], args["water_intents"], args["control"])
            binding = bindings.sources[0]
            self.assertEqual(binding.source_path, ("sources", "source"))
            self.assertIn(expected_path, tuple(p.source_path for p in binding.admission.decision.provenance))

    def test_missing_extent_diagnostic_names_captured_bounds_field(self):
        from app.application.worldData.generators.hydrology.sources.proceduralSourceAdmission import ProceduralSourceAdmissionJob
        args = self.case()
        args["inputs"] = args["inputs"].model_copy(update={"declared_world_bounds": None})
        bindings = ProceduralSourceAdmissionJob().resolve(args["inputs"], args["batch"], args["water_intents"], args["control"])
        self.assertEqual(tuple(issue.path for issue in bindings.sources[0].admission.decision.issues),
                         (("declared_world_bounds",),))


    def without_world_region(self, args):
        plan = args["regions"]
        args["regions"] = plan.model_copy(update={"snapshot": plan.snapshot.model_copy(update={
            "world_region": None, "regions": (plan.snapshot.world_region,)})})
