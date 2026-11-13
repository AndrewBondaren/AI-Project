"""Admission of the independent Pack payload-address contract."""
import unittest

from pydantic import TypeAdapter, ValidationError

from app.dataModel.worldPack.preparation.addresses import (
    PackChunkAddress, PackMapTileAddress, PackPartAddress,
)


class PreparationAddressTests(unittest.TestCase):
    def setUp(self):
        self.adapter = TypeAdapter(PackPartAddress)

    def test_all_roles_round_trip_without_losing_identity(self):
        examples = (
            '{"kind":"map_tile","gx":-2,"gy":3}',
            '{"kind":"wilderness_chunk","gx":-2,"gy":3,"cx":0,"cy":1}',
            '{"kind":"location_terrain","location_uid":"loc-a"}',
            '{"kind":"settlement","location_uid":"loc-a"}',
            '{"kind":"climate_coarse"}',
            '{"kind":"climate_fine","gx":-2,"gy":3}',
            '{"kind":"locations_index"}',
            '{"kind":"spatial_root","domain":"hydrology_open_water"}',
            '{"kind":"tile_grade_slots","gx":-2,"gy":3}',
            '{"kind":"location_grade_slots","location_uid":"loc-a"}',
        )
        values = []
        for wire in examples:
            with self.subTest(wire=wire):
                value = self.adapter.validate_json(wire)
                restored = self.adapter.validate_json(self.adapter.dump_json(value))
                self.assertEqual(type(value), type(restored))
                self.assertEqual(value, restored)
                values.append(value)
        self.assertEqual(len(set(values)), 10)

    def test_strict_coordinates_and_shape(self):
        for wire in (
            '{"kind":"map_tile","gx":true,"gy":0}',
            '{"kind":"map_tile","gx":"1","gy":0}',
            '{"kind":"map_tile","gx":1.0,"gy":0}',
            '{"kind":"map_tile","gx":0,"gy":0,"extra":1}',
            '{"kind":"unknown"}',
            '{"kind":"wilderness_chunk","gx":0,"gy":0,"cx":-1,"cy":0}',
            '{"kind":"location_terrain","location_uid":""}',
            '{"kind":"spatial_root","domain":"unknown"}',
        ):
            with self.subTest(wire=wire), self.assertRaises(ValidationError):
                self.adapter.validate_json(wire)

    def test_forged_instances_are_revalidated(self):
        valid = PackMapTileAddress(kind="map_tile", gx=0, gy=0)
        for forged in (
            valid.model_copy(update={"gx": True}),
            PackChunkAddress.model_construct(kind="wilderness_chunk", gx=0, gy=0, cx=-1, cy=0),
        ):
            with self.subTest(forged=forged), self.assertRaises(ValidationError):
                self.adapter.validate_python(forged)
        with self.assertRaises(ValidationError):
            valid.gx = 1

    def test_independent_coordinate_errors_are_preserved(self):
        with self.assertRaises(ValidationError) as caught:
            PackChunkAddress(kind="wilderness_chunk", gx=True, gy="0", cx=-1, cy=-2)
        self.assertEqual(
            [issue["loc"] for issue in caught.exception.errors()],
            [("gx",), ("gy",), ("cx",), ("cy",)],
        )


if __name__ == "__main__":
    unittest.main()
