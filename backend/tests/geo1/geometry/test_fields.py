"""Resolved algorithm settings, tagged recipes and immutable signed samples."""

from dataclasses import replace
from math import inf, nan
from unittest import TestCase

from pydantic import TypeAdapter, ValidationError

from app.dataModel.spatial.grid.coordinateTypes import GridX, GridY, SurfaceGridCoord
from app.dataModel.terrain.designedWater.fields.field import (
    ContinentalField, NoiseRecipe, PlateRecipe, PlateNoiseRecipe, WaterFieldRecipe,
)
from app.dataModel.terrain.designedWater.settings.continentalNoisePolicy import ContinentalNoisePolicy
from app.dataModel.terrain.designedWater.settings.plateGenerationPolicy import PlateGenerationPolicy
from app.dataModel.terrain.designedWater.settings.fieldCompositionPolicy import FieldCompositionPolicy
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology


def noise_recipe():
    return NoiseRecipe(seed_root="world", topology=WorldTopology(mode=WorldTopologyMode.WRAPPED,
        bounds=WorldBounds(x_min=0, y_min=0, x_max=7, y_max=7)), noise_policy=ContinentalNoisePolicy())


class FieldContractTests(TestCase):
    def test_resolved_policies_have_exact_defaults_and_no_cascade_execution(self):
        self.assertEqual(ContinentalNoisePolicy().model_dump(), dict(length_fraction=0.18, octaves=4,
            lacunarity=2.0, persistence=0.5))
        self.assertEqual(WaterFieldSelectionPolicy().score_bits, 24)
        self.assertEqual(PlateGenerationPolicy().model_dump(), dict(plate_count=12, blend_length_fraction=0.12))
        self.assertEqual(FieldCompositionPolicy().detail_weight, 0.2)
        for model, bad in ((ContinentalNoisePolicy, ({"length_fraction": 0}, {"octaves": True},
                {"octaves": 17}, {"lacunarity": 1}, {"persistence": -0.1}, {"persistence": 1.1},
                {"score_bits": 24}, {"octaves": "4"})),
                (WaterFieldSelectionPolicy, ({"score_bits": 7}, {"score_bits": 31},
                    {"score_bits": True}, {"score_bits": 24.0}, {"score_bits": "24"})),
                (PlateGenerationPolicy, ({"plate_count": 0}, {"plate_count": True}, {"blend_length_fraction": 0})),
                (FieldCompositionPolicy, ({"operator": "add_clamp"}, {"detail_weight": -1}, {"detail_weight": 1.1}))):
            for raw in bad:
                with self.subTest(model=model, raw=raw), self.assertRaises(ValidationError):
                    model.model_validate(raw)
        for value in (nan, inf, -inf, "0.2", True):
            for model, field in ((ContinentalNoisePolicy, "length_fraction"),
                                 (PlateGenerationPolicy, "blend_length_fraction"),
                                 (FieldCompositionPolicy, "detail_weight")):
                with self.subTest(value=value, field=field), self.assertRaises(ValidationError):
                    model.model_validate({field: value})

    def test_recipe_union_has_exact_algorithm_policy_pairs(self):
        noise = noise_recipe()
        plate = PlateRecipe(seed_root=noise.seed_root, topology=noise.topology, plate_policy=PlateGenerationPolicy())
        combined = PlateNoiseRecipe(seed_root=noise.seed_root, topology=noise.topology,
            noise_policy=noise.noise_policy, plate_policy=plate.plate_policy, composition_policy=FieldCompositionPolicy())
        adapter = TypeAdapter(WaterFieldRecipe)
        for recipe in (noise, plate, combined):
            self.assertEqual(adapter.validate_json(adapter.dump_json(recipe)), recipe)
            with self.assertRaises(ValidationError):
                recipe.seed_root = "other"
        for raw in (noise.model_dump() | {"strategy": Strategy.PLATE},
                    combined.model_dump() | {"strategy": Strategy.AUTHORED_REGION},
                    plate.model_dump() | {"noise_policy": noise.noise_policy}):
            with self.assertRaises(ValidationError):
                adapter.validate_python(raw)

    def test_forged_policy_and_topology_instances_are_revalidated(self):
        good = noise_recipe()
        for updates in ({"noise_policy": good.noise_policy.model_copy(update={"octaves": 0})},
                        {"topology": good.topology.model_copy(update={"bounds": good.topology.bounds.model_copy(update={"x_max": -1})})}):
            with self.assertRaises(ValidationError):
                NoiseRecipe.model_validate(good.model_copy(update=updates))

    def test_field_samples_are_signed_finite_unique_and_row_major(self):
        a = SurfaceGridCoord(GridX(0), GridY(0))
        b = SurfaceGridCoord(GridX(1), GridY(0))
        good = ContinentalField(recipe=noise_recipe(), samples=((a, -1.0), (b, 1.0)))
        self.assertEqual(ContinentalField.model_validate_json(good.model_dump_json()), good)
        for samples in (((a, 0.0), (a, 1.0)), ((b, 0.0), (a, 0.0)),
                        *((((a, value),)) for value in (nan, inf, -inf, -1.1, 1.1, True, "0.5")),
                        ((replace(a, gx=True), 0.0),)):
            with self.subTest(samples=samples), self.assertRaises(ValidationError):
                ContinentalField.model_validate(good.model_copy(update={"samples": samples}))

    def test_boundary_preserves_scores_without_selecting_water_or_floor(self):
        field = ContinentalField(recipe=noise_recipe(), samples=((SurfaceGridCoord(GridX(0), GridY(0)), 0.25),))
        self.assertEqual(field.samples[0][1], 0.25)
        self.assertEqual(set(type(field).model_fields), {"recipe", "samples"})
