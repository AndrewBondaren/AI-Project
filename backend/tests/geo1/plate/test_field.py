"""Affine layout, Gaussian blend and shared topology metric checks."""
import builtins
from math import exp,gcd
from unittest import TestCase
from unittest.mock import patch

from pydantic import ValidationError

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.designedWater.fields.plateFieldGenerator import PlateFieldGenerator
from app.dataModel.terrain.designedWater.fields.field import AffinePermutationCoefficient as Coefficient,FieldChannel,PlateRecipe,ContinentalField
from app.dataModel.terrain.designedWater.fields.plateLayout import PlateLayout
from app.dataModel.terrain.designedWater.settings.plateGenerationPolicy import PlateGenerationPolicy
from app.dataModel.terrain.designedWater.strategyKind import WaterDesignIssueCode as Code
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
from app.ids import UidKind,seeded_u01
from tests.geo1.plate.fixtures import case

MODULE="app.application.worldData.generators.terrain.designedWater.fields.plateFieldGenerator"


def recipe(width,height,count):
    return PlateRecipe(seed_root="seed",topology=WorldTopology(mode=Mode.PLANAR,
        bounds=WorldBounds(x_min=0,x_max=width-1,y_min=0,y_max=height-1)),plate_policy=PlateGenerationPolicy(plate_count=count))


def draws(root,kind,**keys):
    if keys["channel"] is FieldChannel.PLATE_CENTER:
        return .5 if keys["coefficient"] is Coefficient.MULTIPLIER else .25
    return .5


class PlateFieldTests(TestCase):
    def test_single_cell_layout_retains_requested_count_and_notice(self):
        value=recipe(1,1,12)
        before=value.model_dump_json()
        layout=PlateFieldGenerator().layout(value)
        self.assertEqual((layout.multiplier,layout.offset,layout.effective_count),(1,0,1))
        self.assertEqual(layout.centers[0].cell,(0,0))
        self.assertEqual(layout.centers[0].buoyancy,2*seeded_u01("seed",UidKind.WATER_FIELD,channel=FieldChannel.PLATE_BUOYANCY,plate_index=0)-1)
        self.assertEqual(layout.notices[0].code,Code.PLATE_COUNT_ADJUSTED.value)
        self.assertEqual(layout.notices[0].path,("plate_policy","plate_count"))
        self.assertIn("requested=12, effective=1",layout.notices[0].message)
        self.assertEqual(value.model_dump_json(),before)
        self.assertEqual(PlateLayout.model_validate_json(layout.model_dump_json()),layout)

    def test_non_coprime_start_scans_cyclically_and_covers_full_world(self):
        with patch(MODULE+".seeded_u01",side_effect=draws):
            layout=PlateFieldGenerator().layout(recipe(4,3,12))
        self.assertEqual((layout.multiplier,layout.offset),(7,3))
        self.assertEqual(gcd(layout.multiplier,12),1)
        self.assertEqual(len({center.cell for center in layout.centers}),12)
        self.assertEqual(tuple(center.cell for center in layout.centers),tuple(((7*i+3)%12%4,(7*i+3)%12//4) for i in range(12)))
        self.assertFalse(layout.notices)

    def test_large_world_enumerates_only_requested_centers(self):
        def bounded_range(n):
            self.assertLessEqual(n,12)
            return builtins.range(n)
        with patch(MODULE+".range",side_effect=bounded_range,create=True):
            layout=PlateFieldGenerator().layout(recipe(1_000_000,1_000_000,12))
        self.assertEqual(layout.effective_count,12)
        self.assertEqual(len({center.cell for center in layout.centers}),12)

    def test_center_prefix_and_buoyancies_are_stable_when_count_changes(self):
        generator=PlateFieldGenerator()
        small=generator.layout(case(policy=PlateGenerationPolicy(plate_count=6)).field_policy)
        large=generator.layout(case(policy=PlateGenerationPolicy(plate_count=12)).field_policy)
        self.assertEqual(small.centers,large.centers[:6])
        self.assertEqual((small.multiplier,small.offset),(large.multiplier,large.offset))

    def test_gaussian_weight_formula_and_equal_distance_blend(self):
        def draw(root,kind,**keys):
            if keys["channel"] is FieldChannel.PLATE_CENTER:return 0.0
            return .25 if keys["plate_index"]==0 else .75
        generator=PlateFieldGenerator()
        with patch(MODULE+".seeded_u01",side_effect=draw):layout=generator.layout(recipe(2,1,2))
        self.assertAlmostEqual(generator.sample(layout,x=.5,y=.5),(-.5+.5*exp(-1))/(1+exp(-1)),places=14)
        self.assertEqual(generator.sample(layout,x=1.0,y=.5),0.0)

    def test_nearest_weight_one_prevents_underflow_failure(self):
        def draw(root,kind,**keys):
            if keys["channel"] is FieldChannel.PLATE_CENTER:
                return .25 if keys["coefficient"] is Coefficient.MULTIPLIER else 0.0
            return .25+.1*keys["plate_index"]
        generator=PlateFieldGenerator()
        with patch(MODULE+".seeded_u01",side_effect=draw):layout=generator.layout(recipe(10000,1,4))
        self.assertEqual(generator.sample(layout,x=.5,y=.5),layout.centers[0].buoyancy)

    def test_build_uses_same_fine_sampler_and_stable_row_order(self):
        generator=PlateFieldGenerator()
        for mode in Mode:
            input=case(mode=mode)
            field=generator.build(input)
            layout=generator.layout(input.field_policy)
            self.assertEqual(tuple(c for c,_ in field.samples),tuple(c for c,_ in input.pre_hydrology.payload.surface_z))
            for cell,value in field.samples:
                self.assertEqual(value,generator.sample(layout,x=(cell.gx+.5)*input.grid.fine_span,y=(cell.gy+.5)*input.grid.fine_span))
                self.assertTrue(-1<=value<=1)
            self.assertEqual(ContinentalField.model_validate_json(field.model_dump_json()),field)

    def test_wrapped_and_sphere_aliases_and_edge_continuity(self):
        generator=PlateFieldGenerator()
        for mode in (Mode.WRAPPED,Mode.SPHERE):
            layout=generator.layout(case(mode=mode).field_policy)
            b=layout.recipe.topology.bounds
            x,y=b.x_min+.5,b.y_min+.5
            self.assertEqual(generator.sample(layout,x=x,y=y),generator.sample(layout,x=x+b.width,y=y))
            if mode is Mode.WRAPPED:
                self.assertEqual(generator.sample(layout,x=x,y=y),generator.sample(layout,x=x,y=y+b.height))
                self.assertAlmostEqual(generator.sample(layout,x=b.x_min-1e-7,y=y),generator.sample(layout,x=b.x_min+1e-7,y=y),places=5)
            else:
                self.assertEqual(generator.sample(layout,x=x,y=b.y_min-.5),generator.sample(layout,x=x+b.width/2,y=b.y_min+.5))
                self.assertEqual(generator.sample(layout,x=x,y=b.y_max+1.5),generator.sample(layout,x=x+b.width/2,y=b.y_max+.5))
                self.assertEqual(generator.sample(layout,x=x,y=float(b.y_min)),generator.sample(layout,x=x+b.width/2,y=float(b.y_min)))
                self.assertAlmostEqual(generator.sample(layout,x=x,y=b.y_min-1e-7),generator.sample(layout,x=x+b.width/2,y=b.y_min+1e-7),places=5)

    def test_seed_blend_and_plate_count_are_real_recipe_inputs(self):
        generator=PlateFieldGenerator()
        input=case();original=generator.build(input)
        for policy in (PlateGenerationPolicy(plate_count=6),PlateGenerationPolicy(blend_length_fraction=.5)):
            self.assertNotEqual(original.samples,generator.build(case(policy=policy)).samples)
        changed=type(input).model_validate(input.model_copy(update={"seed_root":"new-seed",
            "field_policy":input.field_policy.model_copy(update={"seed_root":"new-seed"})}))
        self.assertNotEqual(original.samples,generator.build(changed).samples)
        self.assertEqual(original,generator.build(input))

    def test_field_does_not_use_height_values_fraction_budget_or_source_identity(self):
        generator=PlateFieldGenerator();input=case();expected=generator.build(input)
        source=input.source.model_copy(update={"value":input.source.value.model_copy(update={"source_uid":"another"})})
        terrain=input.pre_hydrology.payload.model_copy(update={"surface_z":tuple((c,z+100) for c,z in input.pre_hydrology.payload.surface_z)})
        changed=type(input).model_validate(input.model_copy(update={"source":source,"metadata":input.metadata.model_copy(update={"source_uid":"another"}),
            "budget":input.budget.model_copy(update={"source_uid":"another"}),
            "context":input.context.model_copy(update={"water_fraction":1.0}),
            "pre_hydrology":input.pre_hydrology.model_copy(update={"payload":terrain})}))
        self.assertEqual(expected,generator.build(changed))

    def test_tampered_layouts_and_nonfinite_positions_are_rejected(self):
        generator=PlateFieldGenerator();layout=generator.layout(recipe(4,3,12))
        for update in ({"multiplier":6},{"offset":12},{"centers":layout.centers[:1]},
                       {"centers":tuple(reversed(layout.centers))}):
            with self.assertRaises(ValidationError):PlateLayout.model_validate(layout.model_copy(update=update))
        for x in (float("nan"),float("inf"),True):
            with self.assertRaises(PlanBuildFailure):generator.sample(layout,x=x,y=.5)
        with self.assertRaises(TypeError):generator.layout({})
