"""Composition arithmetic, component identity and coarse/fine replay."""
from unittest import TestCase
from unittest.mock import patch

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.designedWater.fields.continentalFieldComposer import ContinentalFieldComposer
from app.application.worldData.generators.terrain.designedWater.fields.noiseFieldGenerator import NoiseFieldGenerator
from app.application.worldData.generators.terrain.designedWater.fields.plateFieldGenerator import PlateFieldGenerator
from app.application.worldData.generators.terrain.designedWater.strategies.procedural.plateNoiseStrategy import PlateNoiseStrategy
from app.dataModel.terrain.designedWater.fields.field import ContinentalField
from app.dataModel.terrain.designedWater.settings.fieldCompositionPolicy import FieldCompositionPolicy
from app.dataModel.terrain.designedWater.settings.continentalNoisePolicy import ContinentalNoisePolicy
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from tests.geo1.composition.fixtures import case


class ComposerTests(TestCase):
    def test_formula_both_clamps_and_ordered_notices(self):
        input=case(composition_policy=FieldCompositionPolicy(detail_weight=.5));recipe=input.field_policy
        cells=tuple(c for c,_ in input.pre_hydrology.payload.surface_z)[:4]
        plate=ContinentalField(recipe=recipe.plate_recipe,samples=tuple(zip(cells,(.9,-.9,.1,-.1))),
            notices=(FieldPathError(("plate",),"plate notice"),))
        noise=ContinentalField(recipe=recipe.noise_recipe,samples=tuple(zip(cells,(.8,-.8,-.4,.4))),
            notices=(FieldPathError(("noise",),"noise notice"),))
        result=ContinentalFieldComposer().combine(plate,noise,recipe)
        self.assertEqual(tuple(v for _,v in result.samples),(1.,-1.,-.1,.1))
        self.assertEqual(result.notices,plate.notices+noise.notices)
        self.assertEqual(result.recipe,recipe)

    def test_zero_is_bit_exact_and_never_evaluates_inactive_noise(self):
        input=case(composition_policy=FieldCompositionPolicy(detail_weight=0.),
            noise_policy=ContinentalNoisePolicy(length_fraction=1e308))
        plate=PlateFieldGenerator().build(input)
        with patch.object(NoiseFieldGenerator,"build",side_effect=AssertionError("inactive build")), patch.object(NoiseFieldGenerator,"sample",side_effect=AssertionError("inactive sample")):
            draft=PlateNoiseStrategy().design(input)
            self.assertEqual(draft.field.samples,plate.samples)
            self.assertEqual(draft.field.recipe,input.field_policy)
            layout=PlateFieldGenerator().layout(input.field_policy.plate_recipe)
            self.assertEqual(ContinentalFieldComposer().sample(input.field_policy,layout,x=.5,y=.5),PlateFieldGenerator().sample(layout,x=.5,y=.5))

    def test_component_alignment_and_recipe_mismatches_are_rejected(self):
        input=case();recipe=input.field_policy
        plate=PlateFieldGenerator().build(input);noise=NoiseFieldGenerator().build(input)
        bad_recipe=recipe.noise_recipe.model_copy(update={"seed_root":"other"})
        for bad in (None,noise.model_copy(update={"samples":noise.samples[:-1]}),noise.model_copy(update={"recipe":bad_recipe}),plate):
            with self.assertRaises(PlanBuildFailure):ContinentalFieldComposer().combine(plate,bad,recipe)
        with self.assertRaises(PlanBuildFailure):ContinentalFieldComposer().combine(noise,noise,recipe)
        with self.assertRaises(TypeError):ContinentalFieldComposer().combine({},noise,recipe)

    def test_coarse_samples_equal_fine_evaluation_in_all_topologies(self):
        for mode in Mode:
            input=case(mode=mode);draft=PlateNoiseStrategy().design(input)
            layout=PlateFieldGenerator().layout(input.field_policy.plate_recipe)
            composer=ContinentalFieldComposer()
            for cell,value in draft.field.samples:
                self.assertEqual(value,composer.sample(input.field_policy,layout,
                    x=(cell.gx+.5)*input.grid.fine_span,y=(cell.gy+.5)*input.grid.fine_span))

    def test_topology_aliases_survive_composition(self):
        for mode in (Mode.WRAPPED,Mode.SPHERE):
            recipe=case(mode=mode).field_policy;layout=PlateFieldGenerator().layout(recipe.plate_recipe)
            b=recipe.topology.bounds;composer=ContinentalFieldComposer();x=b.x_min+.5;y=b.y_min+.5
            self.assertEqual(composer.sample(recipe,layout,x=x,y=y),composer.sample(recipe,layout,x=x+b.width,y=y))
            if mode is Mode.WRAPPED:
                self.assertEqual(composer.sample(recipe,layout,x=x,y=y),composer.sample(recipe,layout,x=x,y=y+b.height))
            else:
                self.assertEqual(composer.sample(recipe,layout,x=x,y=b.y_min-.5),composer.sample(recipe,layout,x=x+b.width/2,y=b.y_min+.5))

    def test_weight_and_noise_overrides_change_field_without_changing_plate(self):
        original=case();plate=PlateFieldGenerator().build(original)
        for input in (case(composition_policy=FieldCompositionPolicy(detail_weight=.8)),case(noise_policy=ContinentalNoisePolicy(octaves=1))):
            self.assertEqual(plate,PlateFieldGenerator().build(input))
            self.assertNotEqual(PlateNoiseStrategy().design(original).field.samples,PlateNoiseStrategy().design(input).field.samples)

    def test_seed_is_captured_by_both_components_and_floor_recipe(self):
        input=case()
        changed=type(input).model_validate(input.model_copy(update={"seed_root":"another-seed",
            "field_policy":input.field_policy.model_copy(update={"seed_root":"another-seed"})}))
        draft=PlateNoiseStrategy().design(changed)
        self.assertNotEqual(PlateNoiseStrategy().design(input).field.samples,draft.field.samples)
        self.assertEqual(draft.floor_profile.recipe,changed.field_policy)
        self.assertEqual(changed.field_policy.plate_recipe.seed_root,changed.seed_root)
        self.assertEqual(changed.field_policy.noise_recipe.seed_root,changed.seed_root)
        self.assertNotIn("plate_recipe",changed.field_policy.model_dump())
        self.assertNotIn("noise_recipe",changed.field_policy.model_dump())

    def test_mismatching_layout_and_nonfinite_coordinates_fail(self):
        recipe=case().field_policy;layout=PlateFieldGenerator().layout(recipe.plate_recipe.model_copy(update={"seed_root":"other"}))
        with self.assertRaises(PlanBuildFailure):ContinentalFieldComposer().sample(recipe,layout,x=.5,y=.5)
        layout=PlateFieldGenerator().layout(recipe.plate_recipe)
        with self.assertRaises(PlanBuildFailure):ContinentalFieldComposer().sample(recipe,layout,x=float("nan"),y=.5)
