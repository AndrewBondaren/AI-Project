"""Profile completeness, signed-field identity and canonical coarse output."""

from unittest import TestCase

from pydantic import TypeAdapter, ValidationError

from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace as Space
from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord
from app.dataModel.terrain.designedWater.draft import WaterDesignDraft
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.terrain.relief.bathymetry.floorProfile import SampledFloorProfile
from app.dataModel.validation.immutableValue import validate_immutable
from tests.geo1.contracts.strategies.fixtures import inputs, draft_for

ADAPTER = TypeAdapter(WaterDesignDraft)


class StrategyDraftTests(TestCase):
    def test_variants_roundtrip_without_procedural_footprints(self):
        for strategy in Strategy:
            value = draft_for(inputs(strategy))
            validate_immutable(value)
            self.assertEqual(ADAPTER.validate_json(ADAPTER.dump_json(value)), value)
            absent = "field" if strategy is Strategy.AUTHORED_REGION else "footprints"
            self.assertNotIn(absent, type(value).model_fields)
            with self.assertRaises(ValidationError):
                ADAPTER.validate_python(value.model_dump() | {absent: ()})

    def test_uniform_and_field_floor_must_be_below_level(self):
        for strategy in Strategy:
            value = draft_for(inputs(strategy))
            for floor_z in (0, 2, True):
                with self.subTest(strategy=strategy, z=floor_z), self.assertRaises(ValidationError):
                    ADAPTER.validate_python(value.model_copy(update={"floor_z": floor_z}))
        value = draft_for(inputs())
        for update in ({"floor_z": -6},
                       {"floor_profile": value.floor_profile.model_copy(update={"level": 1})},
                       {"floor_profile": value.floor_profile.model_copy(update={"recipe": inputs(Strategy.PLATE).field_policy})}):
            with self.assertRaises(ValidationError):
                ADAPTER.validate_python(value.model_copy(update=update))

    def test_sampled_floor_requires_exact_footprint_coverage_space_and_minimum(self):
        value = draft_for(inputs(Strategy.AUTHORED_REGION))
        samples = (((-4, 4), -5), ((-3, 4), -2))
        profile = SampledFloorProfile(space=Space.WORLD_FINE_GRID, samples=samples)
        valid = ADAPTER.validate_python(value.model_copy(update={"floor_profile": profile}))
        self.assertEqual(valid.floor_z, -5)
        for update in ({"space": Space.WORLD_SURFACE_GRID}, {"samples": samples[:1]},
                       {"samples": samples + (((-2, 4), -3),)},
                       {"samples": (((-4, 4), -5), ((-3, 4), 0))},
                       {"samples": (((-4, 4), -6), ((-3, 4), -2))}):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                ADAPTER.validate_python(value.model_copy(update={"floor_profile": profile.model_copy(update=update)}))

    def test_authored_geometry_is_nonempty_and_world_space(self):
        value = draft_for(inputs(Strategy.AUTHORED_REGION))
        for update in ({"footprints": ()}, {"footprints": (frozenset(),)},
                       {"coordinate_space": Space.LOCATION_FINE_GRID},
                       {"footprints": (frozenset({(True, 4)}),)}):
            with self.assertRaises(ValidationError):
                ADAPTER.validate_python(value.model_copy(update=update))

    def test_input_checks_field_completeness_order_and_coarse_membership(self):
        value = inputs()
        draft = draft_for(value)
        samples = draft.field.samples
        for bad in (samples[:1], (), samples + ((SurfaceGridCoord(1, 1), 0.0),),
                    ((SurfaceGridCoord(-4, 4), -0.5), (SurfaceGridCoord(0, 4), 0.5)),
                    tuple(reversed(samples)), (samples[0], samples[0])):
            with self.subTest(samples=bad), self.assertRaises(ValueError):
                value.validate_draft(draft.model_copy(update={"field": draft.field.model_copy(update={"samples": bad})}))

    def test_input_rejects_other_strategy_recipe_or_metadata_and_noncanonical_geometry(self):
        for strategy in Strategy:
            value = inputs(strategy)
            draft = draft_for(value)
            with self.assertRaises(ValueError):
                value.validate_draft(draft.model_copy(update={"metadata": draft.metadata.model_copy(update={"source_uid": "other"})}))
            other = inputs(Strategy.PLATE if strategy is not Strategy.PLATE else Strategy.CONTINENTAL_NOISE)
            with self.assertRaises(ValueError):
                value.validate_draft(draft_for(other))
        authored = inputs(Strategy.AUTHORED_REGION)
        with self.assertRaises(ValueError):
            authored.validate_draft(draft_for(authored).model_copy(update={"footprints": (frozenset({(4, 4)}),)}))
        with self.assertRaises(ValueError):
            authored.validate_draft(draft_for(authored).model_copy(update={"floor_z": -6}))
