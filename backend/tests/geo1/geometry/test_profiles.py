"""Floor payload validation; no field evaluation or height writing."""

from unittest import TestCase

from pydantic import TypeAdapter, ValidationError

from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.terrain.relief.bathymetry.floorProfile import (
    BasinFloorProfile, FieldFloorProfile, SampledFloorProfile,
)
from tests.geo1.geometry.test_fields import noise_recipe


class FloorProfileTests(TestCase):
    def test_both_variants_roundtrip_with_explicit_space_or_recipe(self):
        adapter = TypeAdapter(BasinFloorProfile)
        sampled = SampledFloorProfile(space=CoordinateSpace.WORLD_FINE_GRID,
            samples=(((0, 0), FineZ(-3)), ((1, 0), FineZ(-2))))
        field = FieldFloorProfile(recipe=noise_recipe(), level=FineZ(0), depth=10, z_min=FineZ(-20))
        for profile in (sampled, field):
            self.assertEqual(adapter.validate_json(adapter.dump_json(profile)), profile)
            with self.assertRaises(ValidationError):
                adapter.validate_python(profile.model_copy(update={"kind": "unknown"}))

    def test_field_profile_rejects_impossible_floor_and_wrong_units(self):
        raw = dict(recipe=noise_recipe(), level=FineZ(0), depth=10, z_min=FineZ(-20))
        for updates in ({"depth": 0}, {"depth": True}, {"level": False}, {"z_min": 0}, {"z_min": 1},
                        {"recipe": noise_recipe().model_copy(update={"seed_root": ""})}):
            with self.subTest(updates=updates), self.assertRaises(ValidationError):
                FieldFloorProfile.model_validate(raw | updates)

    def test_sampled_payload_rejects_duplicate_unordered_or_coerced_values(self):
        for samples in ((((0, 0), -3), ((0, 0), -2)), (((1, 0), -3), ((0, 0), -2)),
                        (((True, 0), -3),), (((0, 0), False),)):
            with self.subTest(samples=samples), self.assertRaises(ValidationError):
                SampledFloorProfile.model_validate(dict(space=CoordinateSpace.WORLD_SURFACE_GRID, samples=samples))

    def test_sampled_payload_does_not_infer_a_missing_level_or_footprint(self):
        profile = SampledFloorProfile(space=CoordinateSpace.WORLD_FINE_GRID, samples=(((0, 0), FineZ(5)),))
        self.assertEqual(set(type(profile).model_fields), {"kind", "space", "samples"})
        self.assertEqual(profile.samples[0][1], 5)
