"""G5 strategy consumes one geometry result and emits the common draft."""

from unittest import TestCase
from unittest.mock import patch

from pydantic import ValidationError

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.designedWater.strategies.authoredRegionStrategy import AuthoredRegionStrategy
from app.application.worldData.generators.terrain.designedWater.preparation.placementPreparation import DesignedWaterPlacementPreparer
from app.application.worldData.placement.adapters.water import prepare_authored_water_geometry
from app.application.worldData.placement.adapters.waterShape import shape_cells
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.hydrology.sources.waterDesignSource import AuthoredLakeSource, CoastlineWaterSource
from app.dataModel.terrain.designedWater.input import AuthoredWaterDesignInput
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
from tests.geo1.authored.fixtures import request, design_input
from tests.geo1.authored.test_geometry import ring
from tests.geo1.contracts.strategies.fixtures import inputs


class AuthoredStrategyTests(TestCase):
    def test_basin_geometry_is_calculated_once_then_reused_through_common_preparer(self):
        with patch("app.application.worldData.placement.adapters.water.shape_cells", wraps=shape_cells) as geometry:
            input = design_input(request())
            draft = AuthoredRegionStrategy().design(input)
            result = DesignedWaterPlacementPreparer().prepare(input, draft, selection_policy=WaterFieldSelectionPolicy())
            self.assertEqual(geometry.call_count, 1)
        self.assertEqual(draft.floor_z, input.source.value.floor_z)
        self.assertEqual(draft.metadata, input.metadata)
        self.assertEqual(result.candidates[0].footprint.cells, input.geometry.footprints[0])
        self.assertEqual(result.floor_z, draft.floor_z)
        self.assertEqual(result.pre_hydrology_ref, input.pre_hydrology_ref)

    def test_lake_metadata_and_floor_use_precomputed_rim_without_second_geometry_call(self):
        input = design_input(request(AuthoredLakeSource(value=DeclaredLake(location_uid="lake", shoreline=ring()))))
        self.assertEqual(input.metadata.level, 12)
        with patch("app.application.worldData.placement.adapters.water.prepare_authored_water_geometry", side_effect=AssertionError("second rasterization")):
            draft = AuthoredRegionStrategy().design(input)
        self.assertEqual(draft.floor_z, 7)
        self.assertEqual(draft.footprints, input.geometry.footprints)

    def test_coastline_scalar_floor_and_cap_notice_survive_common_preparation(self):
        source = CoastlineWaterSource(value=DeclaredCoastline(location_uid="coast", kind=BasinKind.SEA, path=ring()[:2]))
        input = design_input(request(source, seas=HydrologySeasPolicy(max_area_fraction=0.05)))
        draft = AuthoredRegionStrategy().design(input)
        result = DesignedWaterPlacementPreparer().prepare(input, draft, selection_policy=WaterFieldSelectionPolicy())
        self.assertEqual(draft.floor_z, -5)
        self.assertEqual(result.notices, input.geometry.notices)
        self.assertTrue(result.notices)

    def test_authored_floor_is_never_clamped_and_impossible_floor_has_domain_failure(self):
        input = design_input(request(z_min=-4))
        with self.assertRaises(PlanBuildFailure) as raised:
            AuthoredRegionStrategy().design(input)
        self.assertEqual(raised.exception.issues[0].code, "WATER_PLACEMENT_FLOOR")
        self.assertEqual(input.source.value.floor_z, -5)

    def test_procedural_input_is_not_silently_reinterpreted(self):
        with self.assertRaises(PlanBuildFailure) as raised:
            AuthoredRegionStrategy().design(inputs())
        self.assertEqual(raised.exception.issues[0].code, "WATER_DESIGN_INVALID_STRATEGY")

    def test_geometry_identity_revision_rim_and_canonical_space_must_match_input(self):
        input = design_input(request())
        geometry = input.geometry
        other_ref = geometry.pre_hydrology_ref.model_copy(update={"output_fingerprint": b"x" * 32})
        for update in ({"source_uid": "other"}, {"pre_hydrology_ref": other_ref},
                       {"rim_level": 1}, {"footprints": (frozenset({(-1, 0)}),)}):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                AuthoredWaterDesignInput.model_validate(input.model_copy(update={"geometry": geometry.model_copy(update=update)}))
        lake = design_input(request(AuthoredLakeSource(value=DeclaredLake(location_uid="lake", shoreline=ring()))))
        with self.assertRaises(ValidationError):
            AuthoredWaterDesignInput.model_validate(lake.model_copy(update={"metadata": lake.metadata.model_copy(update={"level": 0})}))

    def test_strategy_revalidates_copied_input_and_preserves_ready_geometry_and_notices(self):
        input = design_input(request())
        before = input.model_dump_json()
        AuthoredRegionStrategy().design(input)
        self.assertEqual(input.model_dump_json(), before)
        with self.assertRaises(PlanBuildFailure):
            AuthoredRegionStrategy().design(input.model_copy(update={"geometry": input.geometry.model_copy(update={"source_uid": "other"})}))
