"""HY-12 step 2: authored wire, policy precedence and parsed basin facts."""

import json
from pathlib import Path
import unittest

from pydantic import ValidationError

from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.types import ImportValidationError
from app.application.worldData.generators.hydrology.basins.seaLevelPolicy import is_land, resolve_z_sea
from app.application.worldData.generators.hydrology.load.buildHydrologyMasterInput import build_hydrology_master_input
from app.application.worldData.generators.hydrology.load.loadDeclaredHydrology import load_declared_hydrology
from app.dataModel.hydrology import BasinKind, DeclaredBasin, DeclaredCoastline, MapCellHydrology, WaterBody, WaterSide, WorldHydrology
from app.dataModel.hydrology.lakes import HydrologyLakesPolicy
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.spatial.regionShape import CorridorShape
from tests.hydrology_fixtures import hydro_world, waypoint


def basin(**overrides):
    return dict(location_uid="basin-a", footprint={"kind": "corridor", "path": [[8, 2], [12, 2]], "width": 2},
                kind="ocean", floor_z=-20) | overrides


class BasinContractTests(unittest.TestCase):
    def test_world_scalar_and_model_defaults(self):
        policy = WorldHydrology()
        self.assertEqual(policy.default_water_level, 0)
        self.assertEqual(policy.declared_basins, [])
        self.assertEqual(policy.default_seas.basin_depth, 20)
        self.assertEqual(policy.default_lakes.basin_depth, 5)
        self.assertEqual(policy.default_seas.max_area_fraction, 0.25)
        self.assertEqual((policy.default_seas.max_extent_x_fraction, policy.default_seas.max_extent_y_fraction), (0.5, 0.5))
        self.assertEqual(policy.default_seas.min_water_cells, 2)
        self.assertEqual(policy.default_lakes.min_water_cells, 2)
        self.assertEqual(policy.default_seas.inland_sea_min_area_fraction, 0.01)

    def test_policy_rejects_supplied_invalid_values(self):
        for model in (HydrologySeasPolicy, HydrologyLakesPolicy):
            for raw in ({"basin_depth": 0}, {"basin_depth": None}, {"min_water_cells": 0}):
                with self.subTest(model=model.__name__, raw=raw), self.assertRaises(ValidationError):
                    model.model_validate(raw)
        for name in ("max_area_fraction", "max_extent_x_fraction", "max_extent_y_fraction", "inland_sea_min_area_fraction"):
            for value in (0, -0.1, 1.01, None):
                with self.subTest(field=name, value=value), self.assertRaises(ValidationError):
                    HydrologySeasPolicy.model_validate({name: value})

    def test_basin_roundtrip_and_registry_key(self):
        entry = DeclaredBasin.model_validate(basin())
        self.assertIsInstance(entry.footprint, CorridorShape)
        self.assertIs(entry.kind, BasinKind.OCEAN)
        self.assertIsInstance(entry.liquid, str)
        self.assertIsNone(entry.z_water_level)
        self.assertIsNone(entry.placement_specificity)
        self.assertEqual(DeclaredBasin.model_validate_json(entry.model_dump_json()), entry)
        self.assertEqual(DeclaredBasin.model_fields["liquid"].default, "water")

    def test_explicit_level_and_inherited_level_validate_strict_floor(self):
        for floor in (7, 8):
            with self.subTest(floor=floor), self.assertRaises(ValidationError):
                DeclaredBasin.model_validate(basin(floor_z=floor, z_water_level=7))
        for floor in (0, 1):
            with self.subTest(floor=floor), self.assertRaises(ValidationError):
                WorldHydrology.model_validate({"declared_basins": [basin(floor_z=floor)]})
        policy = WorldHydrology.model_validate({"default_water_level": 30, "declared_basins": [basin(floor_z=29)]})
        self.assertEqual(policy.declared_basins[0].floor_z, 29)
        self.assertIsNone(policy.declared_basins[0].z_water_level)
        explicit = WorldHydrology.model_validate({"default_water_level": -50,
            "declared_basins": [basin(floor_z=9, z_water_level=10)]})
        self.assertEqual(explicit.declared_basins[0].z_water_level, 10)

    def test_invalid_kind_and_negative_specificity_rejected(self):
        for overrides in ({"kind": "river"}, {"placement_specificity": -1}, {"floor_z": None},
                          {"rim": {"min": 3, "max": 1}}):
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                DeclaredBasin.model_validate(basin(**overrides))

    def test_import_and_patch_keep_author_intent(self):
        normalized = normalize_world({"world_uid": "hy12", "hydrology": {
            "default_water_level": 12, "default_seas": {"basin_depth": 9},
            "declared_basins": [basin(floor_z=5)]}})
        hyd = normalized["hydrology"]
        self.assertEqual(hyd["default_water_level"], 12)
        self.assertEqual(hyd["default_seas"]["basin_depth"], 9)
        self.assertEqual(hyd["declared_basins"][0]["floor_z"], 5)
        patch = normalize_world({"hydrology": {"default_seas": {"basin_depth": 4}}}, partial=True)
        self.assertEqual(patch["hydrology"], {"default_seas": {"basin_depth": 4}})

    def test_import_rejects_invalid_declare(self):
        for raw in (basin(floor_z=0), basin(kind="river"), basin(liquid="stone"),
                    {k: v for k, v in basin().items() if k != "floor_z"}):
            with self.subTest(raw=raw), self.assertRaises(ImportValidationError):
                normalize_world({"world_uid": "hy12", "hydrology": {"declared_basins": [raw]}})

    def test_loader_and_master_preserve_fine_geometry_and_explicit_floor(self):
        world = hydro_world(z_min=-100, fine_cells_per_map_cell=10,
            hydrology={"default_water_level": 12, "default_seas": {"basin_depth": 8},
                       "declared_basins": [basin(floor_z=5)]})
        entry = load_declared_hydrology(world, []).declared_basins[0]
        master = build_hydrology_master_input(world, [])
        self.assertEqual(master.declared_basins, [entry])
        self.assertEqual(entry.footprint.path, [(8, 2), (12, 2)])
        self.assertEqual(entry.floor_z, 5)

    def test_loader_rejects_floor_outside_vertical_bounds_and_nonliquid(self):
        for raw in (basin(floor_z=-101), basin(liquid="stone")):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                load_declared_hydrology(hydro_world(z_min=-100, hydrology={"declared_basins": [raw]}), [])

    def test_scalar_resolve_and_waterline_equality(self):
        self.assertEqual(resolve_z_sea(hydro_world(hydrology={"default_water_level": 13})), 13)
        self.assertEqual(resolve_z_sea(hydro_world()), WorldHydrology().default_water_level)
        self.assertTrue(is_land(13, 13))
        self.assertFalse(is_land(12, 13))

    def test_body_and_cell_preserve_cascade_facts_and_roundtrip(self):
        body = WaterBody(water_body_uid="basin-a", location_uid="location-a", kind=BasinKind.SEA,
                         declared_level=5, z_water_level=8, parent_system_uid="union-a")
        self.assertEqual(WaterBody.model_validate_json(body.model_dump_json()), body)
        cell = MapCellHydrology(role="open_ocean", water_body_uid=body.water_body_uid, z_water_level=8)
        self.assertTrue(cell.liquid_candidate)
        self.assertEqual(MapCellHydrology.model_validate_json(cell.model_dump_json()), cell)
        self.assertIsNone(MapCellHydrology().z_water_level)

    def test_fixture_hy12_basin_and_coastlines_load(self):
        fixture = json.loads((Path(__file__).resolve().parents[2] / "fixtures/world_test_004.json").read_text(encoding="utf-8"))
        world = fixture["world"]
        policy = WorldHydrology.model_validate(world["hydrology"])
        self.assertTrue(policy.declared_basins)
        self.assertIs(policy.declared_coastlines[0].kind, BasinKind.OCEAN)
        loaded = load_declared_hydrology(hydro_world(**({"z_min": None} | {
            k: v for k, v in world.items() if k != "world_uid"})), [])
        self.assertEqual(loaded.declared_basins, policy.declared_basins)

    def test_fixture_imports_accept_explicit_coastline_kind(self):
        root = Path(__file__).resolve().parents[2] / "fixtures"
        for name in ("world_template.json", "world_terrain_test.json", "world_test_all.json", "world_test_004.json"):
            with self.subTest(fixture=name):
                raw = json.loads((root / name).read_text(encoding="utf-8"))["world"]
                normalized = normalize_world(raw)
                policy = WorldHydrology.model_validate(normalized["hydrology"])
                self.assertTrue(policy.declared_coastlines)


class CoastlineContractTests(unittest.TestCase):
    def test_closed_side_and_geometry_are_validated(self):
        raw = {"location_uid": "coast-a", "kind": "sea", "closed": True,
               "path": [waypoint(0, 0), waypoint(4, 0), waypoint(2, 2)]}
        with self.assertRaises(ValidationError):
            DeclaredCoastline.model_validate(raw)
        entry = DeclaredCoastline.model_validate(raw | {"water_side": "interior"})
        self.assertIs(entry.water_side, WaterSide.INTERIOR)
        self.assertEqual(DeclaredCoastline.model_validate_json(entry.model_dump_json()), entry)
        loaded = load_declared_hydrology(hydro_world(hydrology={"declared_coastlines": [entry]}), [])
        self.assertEqual(loaded.coastline_segments[-1], ((2, 2), (0, 0)))

    def test_kind_is_required_and_degenerate_path_is_rejected(self):
        for raw in ({"location_uid": "c", "path": [waypoint(0, 0), waypoint(1, 0)]},
                    {"location_uid": "c", "kind": "sea", "path": [waypoint(0, 0), waypoint(0, 0)]}):
            with self.subTest(raw=raw), self.assertRaises(ValidationError):
                DeclaredCoastline.model_validate(raw)

    def test_nonliquid_coastline_rejected_at_import_and_load(self):
        raw = {"location_uid": "c", "kind": "sea", "liquid": "stone",
               "path": [waypoint(0, 0), waypoint(1, 0)]}
        with self.assertRaises(ImportValidationError):
            normalize_world({"hydrology": {"declared_coastlines": [raw]}})
        with self.assertRaises(ValueError):
            load_declared_hydrology(hydro_world(hydrology={"declared_coastlines": [raw]}), [])


if __name__ == "__main__":
    unittest.main()
