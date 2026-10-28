"""Quantized rank/prefix selection and lossless authored geometry transport."""

from decimal import localcontext
from unittest import TestCase

from pydantic import ValidationError

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.designedWater.preparation.placementPreparation import DesignedWaterPlacementPreparer
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace as Space
from app.dataModel.terrain.designedWater.preparation.result import WaterDesignPreparation
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy, WaterDesignIssueCode as Code
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan, RegionCoverage
from app.dataModel.terrain.relief.bathymetry.floorProfile import SampledFloorProfile
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.validation.immutableValue import validate_immutable
from tests.geo1.contracts.strategies.fixtures import inputs, draft_for
from tests.geo1.preparation.fixtures import procedural_case


class WaterPreparationTests(TestCase):
    def prepare(self, input, draft, *, bits=24):
        return DesignedWaterPlacementPreparer().prepare(input, draft,
            selection_policy=WaterFieldSelectionPolicy(score_bits=bits))

    def cells(self, result):
        return result.candidates[0].footprint.cells

    def test_all_procedural_strategies_share_signed_ranking_and_transport(self):
        for strategy in (Strategy.CONTINENTAL_NOISE, Strategy.PLATE, Strategy.PLATE_NOISE):
            input, draft = procedural_case(strategy=strategy, values=(1.0, -1.0, 0.5, -0.5))
            result = self.prepare(input, draft)
            self.assertEqual(self.cells(result), frozenset({(1, 0), (1, 1)}))
            self.assertEqual(result.original_area, 2.0)
            self.assertEqual(result.coordinate_space, Space.WORLD_SURFACE_GRID)
            self.assertEqual(result.metadata, input.metadata)
            self.assertEqual(result.floor_profile, draft.floor_profile)
            self.assertEqual(result.pre_hydrology_ref, input.pre_hydrology_ref)
            self.assertEqual(result.grid, input.grid)
            self.assertEqual(result.notices, ())

    def test_plate_does_not_require_noise_settings(self):
        input, draft = procedural_case(strategy=Strategy.PLATE)
        self.assertNotIn("noise_policy", type(input.field_policy).model_fields)
        self.assertEqual(len(self.cells(self.prepare(input, draft))), 2)

    def test_equal_score_ties_use_canonical_y_then_x_including_negative_coordinates(self):
        input, draft = procedural_case(bounds=WorldBounds(x_min=-1, x_max=0, y_min=-1, y_max=0))
        self.assertEqual(self.cells(self.prepare(input, draft)), frozenset({(-1, -1), (0, -1)}))

    def test_quantization_is_half_up_and_uses_explicit_common_bits(self):
        bounds = WorldBounds(x_min=0, x_max=1, y_min=0, y_max=0)
        input, draft = procedural_case(allocated=4, bounds=bounds, values=(0.0, -0.001))
        self.assertEqual(self.cells(self.prepare(input, draft, bits=8)), frozenset({(0, 0)}))
        input, draft = procedural_case(allocated=4, bounds=bounds, values=(0.0045, 0.004))
        self.assertEqual(self.cells(self.prepare(input, draft, bits=8)), frozenset({(0, 0)}))
        self.assertEqual(self.cells(self.prepare(input, draft, bits=30)), frozenset({(1, 0)}))
        with localcontext() as ctx:
            ctx.prec = 2
            self.assertEqual(self.cells(self.prepare(input, draft, bits=30)), frozenset({(1, 0)}))

    def test_prefix_equal_error_chooses_smaller_geometry(self):
        input, draft = procedural_case(allocated=6)
        result = self.prepare(input, draft)
        self.assertEqual(self.cells(result), frozenset({(0, 0)}))
        self.assertEqual(result.notices[0].code, Code.COVERAGE_SHORTFALL.value)

    def test_nearest_prefix_can_round_up_without_changing_budget(self):
        input, draft = procedural_case(allocated=3)
        self.assertEqual(len(self.cells(self.prepare(input, draft))), 1)
        self.assertEqual(input.budget.allocated_fine2, 3)

    def test_zero_quota_and_zero_nearest_prefix_do_not_create_phantom_geometry(self):
        for allocated in (0, 1, 2):
            input, draft = procedural_case(allocated=allocated)
            with self.subTest(allocated=allocated), self.assertRaises(PlanBuildFailure) as raised:
                self.prepare(input, draft)
            self.assertEqual(raised.exception.issues[0].code, Code.EMPTY_GENERATION_TARGET.value)

    def test_only_full_region_cells_are_eligible_even_when_partial_cell_has_better_score(self):
        coverage = RegionCoverage(region_uid="region", spans=(CoverageSpan(y=0, x0=0, x1=3), CoverageSpan(y=1, x0=0, x1=3)))
        input, draft = procedural_case(allocated=6, coverage=coverage, values=(1.0, -1.0, -1.0, -1.0))
        result = self.prepare(input, draft)
        self.assertEqual(self.cells(result), frozenset({(0, 0)}))
        self.assertEqual(result.notices[0].code, Code.COVERAGE_SHORTFALL.value)
        self.assertIn("selected_fine2=4", result.notices[0].message)

    def test_all_partial_region_has_explicit_failure_and_no_geometry(self):
        coverage = RegionCoverage(region_uid="region", spans=(CoverageSpan(y=0, x0=0, x1=1),))
        input, draft = procedural_case(allocated=1, coverage=coverage)
        with self.assertRaises(PlanBuildFailure) as raised:
            self.prepare(input, draft)
        self.assertIn("capacity_fine2=0", raised.exception.issues[0].message)

    def test_whole_scope_result_is_stable_on_repeated_preparation_for_all_topologies(self):
        for mode in Mode:
            input, draft = procedural_case(mode=mode, allocated=16)
            result = self.prepare(input, draft)
            self.assertEqual(len(self.cells(result)), 4)
            self.assertEqual(self.prepare(input, draft), result)

    def test_light_side_is_not_used_as_coarse_cell_fine_weight(self):
        input, draft = procedural_case(span=4, allocated=16)
        self.assertEqual(len(self.cells(self.prepare(input, draft))), 1)

    def test_selected_disconnected_cells_remain_one_source_candidate(self):
        input, draft = procedural_case(values=(-1.0, 1.0, 1.0, -1.0))
        result = self.prepare(input, draft)
        self.assertEqual(self.cells(result), frozenset({(0, 0), (1, 1)}))
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].candidate_uid, input.metadata.source_uid)

    def test_authored_geometry_keeps_world_space_and_ignores_procedural_budget(self):
        input = inputs(Strategy.AUTHORED_REGION)
        draft = draft_for(input)
        input = input.model_copy(update={"budget": input.budget.model_copy(update={"allocated_fine2": 0})})
        result = self.prepare(input, draft)
        self.assertEqual(self.cells(result), draft.footprints[0])
        self.assertEqual(result.coordinate_space, Space.WORLD_FINE_GRID)
        self.assertEqual(result.floor_z, input.source.value.floor_z)
        self.assertIsNone(result.floor_profile)

    def test_authored_parts_and_sampled_profile_are_preserved_without_rasterization(self):
        input = inputs(Strategy.AUTHORED_REGION)
        draft = draft_for(input)
        profile = SampledFloorProfile(space=Space.WORLD_FINE_GRID, samples=(((-4, 4), -5), ((-3, 4), -2)))
        draft = draft.model_copy(update={"footprints": (frozenset({(-4, 4)}), frozenset({(-3, 4)})), "floor_profile": profile})
        result = self.prepare(input, draft)
        self.assertEqual(self.cells(result), frozenset({(-4, 4), (-3, 4)}))
        self.assertEqual(result.floor_profile, profile)
        self.assertEqual(result.original_area, 2.0)

    def test_authored_coarse_geometry_keeps_coarse_space(self):
        input = inputs(Strategy.AUTHORED_REGION)
        draft = draft_for(input).model_copy(update={"coordinate_space": Space.WORLD_SURFACE_GRID,
            "footprints": (frozenset({(-1, 1), (0, 1)}),)})
        input = input.model_copy(update={"geometry": input.geometry.model_copy(update={
            "coordinate_space": draft.coordinate_space, "footprints": draft.footprints})})
        result = self.prepare(input, draft)
        self.assertEqual(result.coordinate_space, Space.WORLD_SURFACE_GRID)
        self.assertEqual(self.cells(result), frozenset({(-1, 1), (0, 1)}))

    def test_output_is_immutable_roundtrippable_and_does_not_change_input_height_or_recipe(self):
        input, draft = procedural_case()
        before = (input.model_dump_json(), draft.model_dump_json())
        result = self.prepare(input, draft)
        validate_immutable(result)
        self.assertEqual(WaterDesignPreparation.model_validate_json(result.model_dump_json()), result)
        self.assertEqual(before, (input.model_dump_json(), draft.model_dump_json()))
        with self.assertRaises(ValidationError):
            result.original_area = 99.0
        with self.assertRaises(ValidationError):
            WaterDesignPreparation.model_validate(result.model_copy(update={"floor_z": input.metadata.level}))

    def test_output_revalidation_rejects_lost_profile_geometry_or_coordinate_units(self):
        input, draft = procedural_case()
        result = self.prepare(input, draft)
        for update in ({"original_area": 8.0}, {"floor_profile": None}, {"candidates": ()},
                       {"coordinate_space": Space.LOCATION_FINE_GRID},
                       {"floor_profile": result.floor_profile.model_copy(update={"level": 1})}):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                WaterDesignPreparation.model_validate(result.model_copy(update=update))

    def test_bad_copied_inputs_and_recipes_have_existing_domain_failure_contract(self):
        input, draft = procedural_case()
        for bad_input, bad_draft, policy in (
                (input.model_copy(update={"metadata": {}}), draft, WaterFieldSelectionPolicy()),
                (input, draft.model_copy(update={"metadata": draft.metadata.model_copy(update={"source_uid": "other"})}), WaterFieldSelectionPolicy()),
                (input, draft, WaterFieldSelectionPolicy().model_copy(update={"score_bits": True})),
                (input, draft.model_copy(update={"field": draft.field.model_copy(update={"samples": ()})}), WaterFieldSelectionPolicy())):
            with self.assertRaises(PlanBuildFailure) as raised:
                DesignedWaterPlacementPreparer().prepare(bad_input, bad_draft, selection_policy=policy)
            self.assertEqual(raised.exception.issues[0].code, Code.INVALID_PREPARATION_INPUT.value)

    def test_raw_records_and_missing_policy_cannot_enter_boundary(self):
        input, draft = procedural_case()
        for bad_input, bad_draft, policy in ((input.model_dump(), draft, WaterFieldSelectionPolicy()),
                (input, draft.model_dump(), WaterFieldSelectionPolicy()), (input, draft, {"score_bits": 24})):
            with self.assertRaises(TypeError):
                DesignedWaterPlacementPreparer().prepare(bad_input, bad_draft, selection_policy=policy)
        with self.assertRaises(TypeError):
            DesignedWaterPlacementPreparer().prepare(input, draft)
