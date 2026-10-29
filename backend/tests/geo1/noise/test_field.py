"""Analytical lattice/fBm checks, coordinate embeddings and exact fine/coarse sampling."""
from math import fsum,isfinite
from unittest import TestCase

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.designedWater.fields.noiseFieldGenerator import NoiseFieldGenerator
from app.dataModel.terrain.designedWater.fields.field import FieldChannel,ContinentalField
from app.dataModel.terrain.designedWater.settings.continentalNoisePolicy import ContinentalNoisePolicy
from app.dataModel.terrain.designedWater.strategyKind import WaterDesignIssueCode
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
from app.dataModel.topology.worldBounds import WorldBounds
from app.ids import UidKind,seeded_u01
from tests.geo1.noise.fixtures import case


def vertex(recipe,octave,coords):
    return 2*seeded_u01(recipe.seed_root,UidKind.WATER_FIELD,channel=FieldChannel.NOISE_LATTICE,octave=octave,lattice=coords)-1


class NoiseFieldTests(TestCase):
    def test_planar_lattice_corner_uses_named_noise_channel(self):
        input=case(policy=ContinentalNoisePolicy(octaves=1,length_fraction=0.001))
        self.assertEqual(NoiseFieldGenerator().sample(input.field_policy,x=0.0,y=0.0),vertex(input.field_policy,0,(0,0)))

    def test_quintic_bilinear_interpolation_matches_formula(self):
        input=case(policy=ContinentalNoisePolicy(octaves=1,length_fraction=0.001))
        x,y=0.25,0.5
        q=lambda t:6*t**5-15*t**4+10*t**3
        expected=fsum(vertex(input.field_policy,0,(i,j))*(q(x) if i else 1-q(x))*(q(y) if j else 1-q(y)) for i in (0,1) for j in (0,1))
        self.assertAlmostEqual(NoiseFieldGenerator().sample(input.field_policy,x=x,y=y),expected,places=14)

    def test_fbm_is_normalized_weighted_octaves(self):
        input=case(policy=ContinentalNoisePolicy(octaves=3,persistence=0.5,length_fraction=0.001))
        expected=fsum(vertex(input.field_policy,k,(0,0))*0.5**k for k in range(3))/fsum(0.5**k for k in range(3))
        self.assertEqual(NoiseFieldGenerator().sample(input.field_policy,x=0.0,y=0.0),expected)

    def test_zero_weight_octaves_are_not_evaluated(self):
        input=case(policy=ContinentalNoisePolicy(octaves=16,persistence=0.0,lacunarity=1e300,length_fraction=0.001))
        self.assertEqual(NoiseFieldGenerator().sample(input.field_policy,x=0.0,y=0.0),vertex(input.field_policy,0,(0,0)))

    def test_every_coarse_sample_matches_same_world_fine_sampler(self):
        generator=NoiseFieldGenerator()
        for mode in Mode:
            input=case(mode=mode)
            field=generator.build(input)
            self.assertEqual(tuple(c for c,_ in field.samples),tuple(c for c,_ in input.pre_hydrology.payload.surface_z))
            for c,value in field.samples:
                self.assertEqual(value,generator.sample(input.field_policy,x=(c.gx+.5)*input.grid.fine_span,y=(c.gy+.5)*input.grid.fine_span))
            self.assertEqual(ContinentalField.model_validate_json(field.model_dump_json()),field)

    def test_wrapped_aliases_are_exact_at_centers_and_continuous_at_seams(self):
        recipe=case(mode=Mode.WRAPPED).field_policy
        b=recipe.topology.bounds
        generator=NoiseFieldGenerator()
        value=generator.sample(recipe,x=b.x_min+.5,y=b.y_min+.5)
        for dx,dy in ((b.width,0),(-2*b.width,b.height),(0,-b.height)):
            self.assertEqual(value,generator.sample(recipe,x=b.x_min+.5+dx,y=b.y_min+.5+dy))
        for axis in (0,1):
            x,y=float(b.x_min),float(b.y_min)
            left=generator.sample(recipe,x=x-1e-7 if axis==0 else x,y=y-1e-7 if axis==1 else y)
            right=generator.sample(recipe,x=x+1e-7 if axis==0 else x,y=y+1e-7 if axis==1 else y)
            self.assertAlmostEqual(left,right,places=5)

    def test_sphere_fold_and_pole_aliases(self):
        recipe=case(mode=Mode.SPHERE).field_policy
        b=recipe.topology.bounds
        generator=NoiseFieldGenerator()
        for pole in (float(b.y_min),float(b.y_max+1)):
            values=tuple(generator.sample(recipe,x=b.x_min+offset,y=pole) for offset in (0.0,.5,1.5,b.width/2))
            self.assertTrue(all(value==values[0] for value in values))
        x=b.x_min+.5
        for y,folded in ((b.y_min-.5,b.y_min+.5),(b.y_max+1.5,b.y_max+.5)):
            self.assertEqual(generator.sample(recipe,x=x,y=y),generator.sample(recipe,x=x+b.width/2,y=folded))
        for y in (b.y_min+.5,b.y_max+.5):
            self.assertEqual(generator.sample(recipe,x=x,y=y),generator.sample(recipe,x=x+b.width,y=y+2*b.height))

    def test_tiny_negative_worlds_and_field_range(self):
        generator=NoiseFieldGenerator()
        for mode in Mode:
            for bounds in (WorldBounds(x_min=0,x_max=0,y_min=0,y_max=0),WorldBounds(x_min=-5,x_max=-4,y_min=-3,y_max=-2)):
                input=case(mode=mode,bounds=bounds,span=1)
                field=generator.build(input)
                self.assertTrue(all(isfinite(v) and -1<=v<=1 for _,v in field.samples))
        policy=ContinentalNoisePolicy(octaves=16,persistence=1.0)
        self.assertTrue(all(-1<=v<=1 for _,v in generator.build(case(policy=policy)).samples))

    def test_seed_and_settings_changes_are_real_inputs(self):
        generator=NoiseFieldGenerator()
        input=case()
        original=generator.build(input)
        for policy in (ContinentalNoisePolicy(length_fraction=.5),ContinentalNoisePolicy(octaves=1),
                       ContinentalNoisePolicy(lacunarity=3.0),ContinentalNoisePolicy(persistence=.8)):
            self.assertNotEqual(original.samples,generator.build(case(policy=policy)).samples)
        changed=type(input).model_validate(input.model_copy(update={"seed_root":"new-seed",
            "field_policy":input.field_policy.model_copy(update={"seed_root":"new-seed"})}))
        self.assertNotEqual(original.samples,generator.build(changed).samples)
        self.assertEqual(original,generator.build(input))

    def test_sampler_order_and_unrelated_source_identity_do_not_change_world_field(self):
        generator=NoiseFieldGenerator()
        input=case()
        points=((.5,.5),(1.5,2.5),(-1.5,.5))
        expected={p:generator.sample(input.field_policy,x=p[0],y=p[1]) for p in points}
        self.assertEqual(expected,{p:generator.sample(input.field_policy,x=p[0],y=p[1]) for p in reversed(points)})
        source=input.source.model_copy(update={"value":input.source.value.model_copy(update={"source_uid":"another"})})
        changed=type(input).model_validate(input.model_copy(update={"source":source,
            "metadata":input.metadata.model_copy(update={"source_uid":"another"}),
            "budget":input.budget.model_copy(update={"source_uid":"another"})}))
        self.assertEqual(generator.build(input),generator.build(changed))

    def test_budget_fraction_and_height_values_do_not_affect_the_field(self):
        generator=NoiseFieldGenerator()
        input=case()
        expected=generator.build(input)
        changed_surface=input.pre_hydrology.payload.model_copy(update={"surface_z":tuple((c,z+100) for c,z in input.pre_hydrology.payload.surface_z)})
        changed=type(input).model_validate(input.model_copy(update={"context":input.context.model_copy(update={"water_fraction":1.0}),
            "budget":input.budget.model_copy(update={"allocated_fine2":0}),
            "pre_hydrology":input.pre_hydrology.model_copy(update={"payload":changed_surface})}))
        self.assertEqual(expected,generator.build(changed))

    def test_nonfinite_or_unrepresentable_sampling_is_typed_failure(self):
        generator=NoiseFieldGenerator()
        input=case()
        for x in (float("nan"),float("inf"),True):
            with self.assertRaises(PlanBuildFailure):generator.sample(input.field_policy,x=x,y=0.0)
        overflow=case(policy=ContinentalNoisePolicy(lacunarity=1e300))
        with self.assertRaises(PlanBuildFailure) as caught:generator.build(overflow)
        self.assertEqual(caught.exception.issues[0].code,WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value)
        with self.assertRaises(TypeError):generator.build({})
