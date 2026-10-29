"""Real noise draft and the existing single prefix boundary, without policy or height writes."""
from unittest import TestCase
from unittest.mock import patch

from pydantic import ValidationError

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.designedWater.strategies.procedural.continentalNoiseStrategy import ContinentalNoiseStrategy
from app.application.worldData.generators.terrain.designedWater.fields.noiseFieldGenerator import NoiseFieldGenerator
from app.application.worldData.generators.terrain.designedWater.preparation.placementPreparation import DesignedWaterPlacementPreparer
from app.application.worldData.generators.terrain.designedWater.coverage.waterCoverageBudgetPolicy import WaterCoverageBudgetPolicy
from app.application.policy.policyResolver import PolicyResolver
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationScope as Scope
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageRequest
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy,WaterDesignIssueCode as Code
from app.dataModel.terrain.designedWater.draft import ProceduralWaterDesignDraft
from app.dataModel.terrain.relief.bathymetry.floorProfile import FieldFloorProfile
from app.dataModel.topology.worldBounds import WorldBounds
from tests.geo1.noise.fixtures import case
from tests.geo1.contracts.strategies.fixtures import inputs
from tests.geo1.coastline_source.fixtures import capture,prepare


class NoiseStrategyTests(TestCase):
    def test_ready_metadata_and_actual_world_floor_profile_are_preserved(self):
        input=case()
        before=input.model_dump_json()
        draft=ContinentalNoiseStrategy().design(input)
        self.assertEqual(draft.metadata,input.metadata)
        self.assertEqual(draft.field,NoiseFieldGenerator().build(input))
        self.assertEqual(draft.floor_profile.recipe,input.field_policy)
        self.assertEqual(draft.floor_profile.z_min,input.z_min)
        self.assertEqual(draft.floor_profile.depth,input.metadata.default_depth)
        self.assertEqual(draft.floor_z,max(input.z_min,input.metadata.level-input.metadata.default_depth))
        self.assertNotIn("footprints",type(draft).model_fields)
        self.assertNotIn("candidates",type(draft).model_fields)
        self.assertEqual(input.model_dump_json(),before)
        self.assertEqual(ProceduralWaterDesignDraft.model_validate_json(draft.model_dump_json()),draft)

    def test_floor_uses_world_bound_not_minimum_terrain_height(self):
        input=case()
        changed=type(input).model_validate(input.model_copy(update={"z_min":-3}))
        draft=ContinentalNoiseStrategy().design(changed)
        self.assertEqual(draft.floor_z,-3)
        self.assertEqual(draft.floor_profile.z_min,-3)
        for z in (0,1,True,-20.0):
            with self.assertRaises(ValidationError):type(input).model_validate(input.model_copy(update={"z_min":z}))

    def test_z_min_is_required_for_all_procedural_variants(self):
        for strategy in (Strategy.CONTINENTAL_NOISE,Strategy.PLATE,Strategy.PLATE_NOISE):
            input=inputs(strategy)
            data=dict(input);data.pop("z_min")
            with self.assertRaises(ValidationError):type(input).model_validate(data)

    def test_input_rejects_profile_depth_or_world_bound_substitution(self):
        input=case()
        draft=ContinentalNoiseStrategy().design(input)
        for profile in (draft.floor_profile.model_copy(update={"z_min":-30}),
                        draft.floor_profile.model_copy(update={"depth":6})):
            floor=max(profile.z_min,profile.level-profile.depth)
            changed=type(draft).model_validate(draft.model_copy(update={"floor_profile":profile,"floor_z":floor}))
            with self.assertRaises(ValueError):input.validate_draft(changed)

    def test_zero_sixty_and_full_quota_use_only_common_budget_and_prefix(self):
        fields=[]
        for fraction,expected in ((0.0,0),(.6,15),(1.0,25)):
            input=case(bounds=WorldBounds(x_min=0,x_max=4,y_min=0,y_max=4))
            context=input.context.model_copy(update={"level":Scope.WORLD,"water_fraction":fraction})
            budget=WaterCoverageBudgetPolicy().calculate(input.region,context,
                (BodyCoverageRequest(source_uid=input.metadata.source_uid,generation_region_uid=input.region.region_uid,
                    generation_area_fine2=input.region.generation_area_fine2,target_fraction=fraction),),
                authored_union_fine2=0,available_auto_area_fine2=input.region.generation_area_fine2)
            input=type(input).model_validate(input.model_copy(update={"context":input.context.model_copy(update={"water_fraction":fraction}),"budget":budget.allocations[0]}))
            draft=ContinentalNoiseStrategy().design(input);fields.append(draft.field)
            if expected==0:
                with self.assertRaises(PlanBuildFailure) as caught:
                    DesignedWaterPlacementPreparer().prepare(input,draft,selection_policy=WaterFieldSelectionPolicy())
                self.assertEqual(caught.exception.issues[0].code,Code.EMPTY_GENERATION_TARGET.value)
            else:
                result=DesignedWaterPlacementPreparer().prepare(input,draft,selection_policy=WaterFieldSelectionPolicy())
                self.assertEqual(len(result.candidates[0].footprint.cells),expected)
        self.assertEqual(fields[0],fields[1]);self.assertEqual(fields[1],fields[2])

    def test_real_noise_coastline_preserves_captured_constraints(self):
        input=prepare(capture())
        draft=ContinentalNoiseStrategy().design(input)
        result=DesignedWaterPlacementPreparer().prepare(input,draft,selection_policy=WaterFieldSelectionPolicy())
        self.assertTrue(input.constraints.required_cells <= result.candidates[0].footprint.cells <= input.constraints.allowed_cells)
        self.assertEqual(result.floor_profile,draft.floor_profile)
        self.assertEqual(draft.metadata.source_uid,input.source.value.location_uid)

    def test_strategy_does_not_resolve_policy_budget_or_spatial_selection(self):
        input=case()
        with patch.object(PolicyResolver,"resolve",side_effect=AssertionError("policy")),              patch.object(WaterCoverageBudgetPolicy,"calculate",side_effect=AssertionError("budget")),              patch.object(DesignedWaterPlacementPreparer,"prepare",side_effect=AssertionError("selection")):
            ContinentalNoiseStrategy().design(input)

    def test_wrong_strategy_and_invalid_copied_inputs_are_typed_errors(self):
        strategy=ContinentalNoiseStrategy()
        for input in (inputs(Strategy.AUTHORED_REGION),inputs(Strategy.PLATE),inputs(Strategy.PLATE_NOISE)):
            with self.assertRaises(PlanBuildFailure) as caught:strategy.design(input)
            self.assertEqual(caught.exception.issues[0].code,Code.INVALID_STRATEGY.value)
        input=case()
        with self.assertRaises(PlanBuildFailure):strategy.design(input.model_copy(update={"z_min":None}))
