"""HY-12 review-debt step 5: validated updates retain future POJO fields."""

import unittest

from pydantic import Field, ValidationError, model_validator

from app.application.worldData.generators.hydrology.types import RiverSegment
from app.application.worldData.generators.terrain.worldMapSettings import world_z_min
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.physicalWaterUnion import PhysicalWaterUnion
from app.dataModel.hydrology.waterBody import WaterBody
from tests.hydrology_fixtures import heightmap_from_z, hydro_world
from tests.hydrology_geometry_helpers import apply_test_river


class FutureUnion(PhysicalWaterUnion):
    revision: int

    @model_validator(mode="after")
    def check_future_rule(self):
        if self.z_water_level > self.revision:
            raise ValueError("future level rule")
        return self


class FutureBody(WaterBody):
    revision: int = Field(alias="schema_revision")

    @model_validator(mode="after")
    def check_future_rule(self):
        if self.parent_system_uid == "rejected-parent":
            raise ValueError("future parent rule")
        return self


class FutureCell(MapCellHydrology):
    revision: int

    @model_validator(mode="after")
    def check_future_rule(self):
        if self.z_water_level is not None and self.z_water_level > self.revision:
            raise ValueError("future level rule")
        return self


def union(model=PhysicalWaterUnion, **extra):
    return model(water_system_uid="union", member_uids=("left", "right"),
                 child_system_uids=("child",), z_water_level=8, parent_system_uid="outer", **extra)


def body(model=WaterBody, **extra):
    return model(water_body_uid="lake", location_uid="lake-location", kind=BasinKind.LAKE,
                 liquid="water", declared_level=10, z_water_level=8,
                 declared_basin_uid="basin", parent_system_uid="union", **extra)


def cell(model=MapCellHydrology, **extra):
    return model(role=HydrologyCellRole.LAKE, deepening_index=3, water_body_uid="lake",
                 connection_edge_uid="edge", z_water_level=8, **extra)


class ValidatedHydrologyUpdateTests(unittest.TestCase):
    def test_all_updates_keep_required_future_field_and_original_values(self):
        u, b, c = union(FutureUnion, revision=20), body(FutureBody, schema_revision=20), cell(FutureCell, revision=20)
        cases = (
            (u, "with_identity", ("new-union", ("a", "b")), {"water_system_uid": "new-union", "member_uids": ("a", "b")}),
            (u, "with_parent_system", ("new-parent",), {"parent_system_uid": "new-parent"}),
            (u, "with_parent_system", (None,), {"parent_system_uid": None}),
            (u, "with_child_systems", (("child-a", "child-b"),), {"child_system_uids": ("child-a", "child-b")}),
            (u, "with_water_level", (12,), {"z_water_level": 12}),
            (b, "with_parent_system", ("new-parent",), {"parent_system_uid": "new-parent"}),
            (b, "with_parent_system", (None,), {"parent_system_uid": None}),
            (c, "with_water_level", (12,), {"z_water_level": 12}),
        )
        for original, method, args, expected in cases:
            with self.subTest(model=type(original).__name__, method=method, args=args):
                before = original.model_dump(round_trip=True)
                result = getattr(original, method)(*args)
                self.assertIs(type(result), type(original))
                self.assertIsNot(result, original)
                self.assertEqual(result.model_dump(round_trip=True), before | expected)
                self.assertEqual(original.model_dump(round_trip=True), before)

    def test_invalid_updates_remain_validation_errors(self):
        cases = (
            (union(), "with_identity", (123, ("a",))),
            (union(), "with_identity", ("valid", (123,))),
            (union(), "with_parent_system", (123,)),
            (union(), "with_child_systems", ((123,),)),
            (union(), "with_water_level", (None,)),
            (body(), "with_parent_system", (123,)),
            (cell(), "with_water_level", ("invalid",)),
        )
        for original, method, args in cases:
            with self.subTest(model=type(original).__name__, method=method):
                before = original.model_dump(round_trip=True)
                with self.assertRaises(ValidationError):
                    getattr(original, method)(*args)
                self.assertEqual(original.model_dump(round_trip=True), before)

    def test_model_validators_run_on_updates(self):
        cases = (
            (union(FutureUnion, revision=20), "with_water_level", (21,)),
            (body(FutureBody, schema_revision=20), "with_parent_system", ("rejected-parent",)),
            (cell(FutureCell, revision=20), "with_water_level", (21,)),
        )
        for original, method, args in cases:
            with self.subTest(model=type(original).__name__):
                with self.assertRaisesRegex(ValidationError, "future .* rule"):
                    getattr(original, method)(*args)

    def test_cell_role_normalization_is_preserved(self):
        for role in (HydrologyCellRole.LAKE, HydrologyCellRole.SHORE):
            with self.subTest(role=role):
                original = MapCellHydrology(role=role, water_body_uid="body", z_water_level=8)
                result = original.with_water_level(9)
                self.assertEqual(result.role, original.role)
                self.assertEqual(result.liquid_candidate, role is HydrologyCellRole.LAKE)

    def test_test_adapter_requires_explicit_floor_and_respects_negative_world_floor(self):
        hm = heightmap_from_z({(0, 0): -10, (1, 0): -25})
        segment = RiverSegment([(0, 0), (1, 0)], "river")
        with self.assertRaises(TypeError):
            apply_test_river(hm, segment, depth_step=3)
        result = apply_test_river(hm, segment, depth_step=3, z_min=world_z_min(hydro_world(z_min=-20)))
        self.assertEqual(hm.surface_z, {(0, 0): -13, (1, 0): -25})
        self.assertEqual(set(result), {(0, 0), (1, 0)})


if __name__ == "__main__":
    unittest.main()
