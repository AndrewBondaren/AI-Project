from unittest import TestCase
from unittest.mock import patch

from pydantic import ValidationError

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.designedWater.fields.continentalFieldComposer import ContinentalFieldComposer
from app.application.worldData.generators.terrain.designedWater.fields.noiseFieldGenerator import NoiseFieldGenerator
from app.application.worldData.generators.terrain.designedWater.fields.plateFieldGenerator import PlateFieldGenerator
from app.application.worldData.generators.terrain.designedWater.preparation.coastlineWaterSourceAdapter import CoastlineWaterSourceAdapter
from app.dataModel.terrain.designedWater.fields.field import FineContinentalField, NoiseRecipe, PlateRecipe
from app.dataModel.terrain.designedWater.geometry.authoredGeometry import AuthoredWaterGeometryRequest
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from tests.geo1.coastline_source.fixtures import capture
from tests.geo1.fine_water.fixtures import physical_inputs
from tests.geo1.fine_water.test_fill import source as fine_window


class NativeFieldTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.window, _, cls.topology = fine_window(hills=False)

    def admitted(self, strategy):
        value = capture(strategy=strategy)
        legacy = value.geometry_request
        request = AuthoredWaterGeometryRequest(source=legacy.source, pre_hydrology=self.window,
            topology=self.topology, grid=physical_inputs(self.topology).grid, seed_root=legacy.seed_root,
            anchors=(), seas=legacy.seas, z_min=legacy.z_min)
        return CoastlineWaterSourceAdapter().prepare_native(**dict(vars(value), geometry_request=request,
            expected_window=self.window.ref, field_policy=value.field_policy.model_copy(update={"topology": self.topology})))

    def test_fields_cover_window_and_match_independent_fine_samples(self):
        composer = ContinentalFieldComposer()
        for strategy in (Strategy.CONTINENTAL_NOISE, Strategy.PLATE, Strategy.PLATE_NOISE):
            with self.subTest(strategy=strategy):
                admitted = self.admitted(strategy)
                self.assertGreater(admitted.grid.fine_span, 1)
                field = composer.build_native(admitted)
                recipe = admitted.field_policy
                self.assertEqual(field.pre_hydrology_ref, self.window.ref)
                self.assertEqual(field.recipe, recipe)
                self.assertEqual(tuple(c for c, _ in field.samples), tuple(c for c, _ in self.window.payload.surface_z))
                values = dict(field.samples)
                if not isinstance(recipe, NoiseRecipe):
                    plates = PlateFieldGenerator()
                    layout = plates.layout(recipe if isinstance(recipe, PlateRecipe) else recipe.plate_recipe)
                    self.assertEqual(field.notices, layout.notices)
                for x in (0, 1):
                    position = dict(x=x + 0.5, y=0.5)
                    if isinstance(recipe, NoiseRecipe):
                        expected = NoiseFieldGenerator().sample(recipe, **position)
                    elif isinstance(recipe, PlateRecipe):
                        expected = plates.sample(layout, **position)
                    else:
                        expected = composer.sample(recipe, layout, **position)
                    self.assertEqual(values[(x, 0)], expected)
                self.assertNotEqual(values[(0, 0)], values[(1, 0)])

    def test_zero_weight_skips_noise_and_field_rejects_missing_or_swapped_cells(self):
        admitted = self.admitted(Strategy.PLATE_NOISE)
        policy = admitted.field_policy
        recipe = policy.model_copy(update={"composition_policy": policy.composition_policy.model_copy(
            update={"detail_weight": 0.0})})
        composer = ContinentalFieldComposer()
        with patch.object(NoiseFieldGenerator, "fine_values", side_effect=AssertionError("unused noise")):
            field = composer.build_native(admitted.model_copy(update={"field_policy": recipe}))
        self.assertEqual(field.samples, composer.build_native(self.admitted(Strategy.PLATE)).samples)
        for invalid in (field.samples[:-1], (field.samples[1], field.samples[0], *field.samples[2:])):
            with self.assertRaises(ValidationError):
                FineContinentalField.model_validate(field.model_copy(update={"samples": invalid}))

    def test_stale_constraints_rejected_before_sampling(self):
        admitted = self.admitted(Strategy.CONTINENTAL_NOISE)
        stale = self.window.ref.model_copy(update={"output_fingerprint": bytes(32)})
        constraints = admitted.constraints.model_copy(update={"pre_hydrology_ref": stale})
        with patch.object(NoiseFieldGenerator, "fine_values", side_effect=AssertionError("sampling")):
            with self.assertRaises(PlanBuildFailure) as caught:
                ContinentalFieldComposer().build_native(admitted.model_copy(update={"constraints": constraints}))
        self.assertEqual([(i.path, i.code) for i in caught.exception.issues], [
            (("continental_field", "constraints", "pre_hydrology_ref"), "WATER_DESIGN_INVALID_PREPARATION_INPUT")])
