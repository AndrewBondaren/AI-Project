"""Unit tests for hydrology pure helpers — D HY-1."""

from app.application.jsonValidation.resolve import UnresolvedModelError, ResolveContext, resolve_result
import unittest

from app.application.worldData.generators.hydrology.load.loadHydrologyFromWorld import (
    is_hydrology_enabled,
)
from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.types import ImportValidationError
from app.application.jsonValidation.worldRow import hydrology
from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.hydrology.rivers import RiverTypeClassify
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.application.worldData.generators.hydrology.rivers.classifyRiverSegments import classify_river_type
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.application.worldData.generators.hydrology.load.resolveRiverTypeClassify import (
    resolve_river_type_classify,
)
from app.application.worldData.generators.hydrology.load.buildHydrologyMasterInput import (
    build_hydrology_master_input,
)
from app.application.worldData.generators.hydrology.load.hydrologyLocations import (
    geographic_locations,
    is_geographic_location,
)
from app.application.worldData.generators.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.db.models.namedLocation import NamedLocation
from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.terrain.types import SurfaceHeightmap


from tests.hydrology_fixtures import hydro_world as _world
from tests.hydrology_fixtures import heightmap_from_z


class TestHydrologyBands(unittest.TestCase):

    def test_missing_category_bands_preserve_category_defaults(self):
        wire = normalize_world({"hydrology": {}})["hydrology"]
        policy = hydrology(_world(hydrology=wire))
        self.assertEqual(policy.default_rivers.bands, HydrologyBands(min=1, max=5))
        self.assertEqual(policy.default_lakes.bands, HydrologyBands(min=1, max=5))
        self.assertEqual(policy.default_seas.bands, HydrologyBands(min=1, max=20))
        self.assertIsNone(policy.default_landforms.bands)

    def test_partial_bands_use_pojo_default_max_instead_of_legacy_99(self):
        for category in ("default_rivers", "default_lakes", "default_seas", "default_landforms"):
            with self.subTest(category=category):
                wire = normalize_world({"hydrology": {category: {"bands": {"min": 3}}}})["hydrology"]
                bands = getattr(hydrology(_world(hydrology=wire)), category).bands
                self.assertEqual(bands, HydrologyBands(min=3, max=5))

    def test_custom_bands_roundtrip_through_import_and_runtime(self):
        wire = normalize_world({"hydrology": {
            "default_rivers": {"bands": {"min": 2, "max": 8}},
            "default_seas": {"bands": {"min": 7, "max": 30}},
        }})["hydrology"]
        policy = hydrology(_world(hydrology=wire))
        self.assertIsInstance(policy.default_rivers.bands, HydrologyBands)
        self.assertEqual(policy.default_rivers.bands, HydrologyBands(min=2, max=8))
        self.assertEqual(policy.default_seas.bands, HydrologyBands(min=7, max=30))
        self.assertEqual(WorldHydrology.model_validate_json(policy.model_dump_json()), policy)

    def test_invalid_supplied_bounds_are_rejected_without_clamp_or_default(self):
        for field, value in (("min", 0), ("min", -1), ("max", 100), ("max", None), ("max", 8.5)):
            with self.subTest(field=field, value=value):
                raw = {"default_rivers": {"bands": {"min": 2, "max": 8, field: value}}}
                with self.assertRaises(ImportValidationError):
                    normalize_world({"hydrology": raw})
                with self.assertRaises(UnresolvedModelError):
                    hydrology(_world(hydrology=raw))

    def test_typed_rim_is_preserved_and_inverted_rim_rejected(self):
        basin = {"location_uid": "basin", "kind": "lake", "floor_z": -8, "z_water_level": 0,
                 "footprint": {"kind": "bbox", "x_min": 0, "x_max": 3, "y_min": 0, "y_max": 3},
                 "rim": {"min": 2, "max": 7}}
        raw = {"declared_basins": [basin]}
        normalized = normalize_world({"hydrology": raw})["hydrology"]
        self.assertEqual(hydrology(_world(hydrology=normalized)).declared_basins[0].rim,
                         HydrologyBands(min=2, max=7))
        invalid = {"declared_basins": [{**basin, "rim": {"min": 7, "max": 2}}]}
        with self.assertRaises(ImportValidationError):
            normalize_world({"hydrology": invalid})
        with self.assertRaises(UnresolvedModelError):
            hydrology(_world(hydrology=invalid))


class TestRiverTypeClassify(unittest.TestCase):

    def test_missing_policy_returns_canonical_pojo_defaults(self):
        wire = normalize_world({"hydrology": {}})["hydrology"]
        result = resolve_river_type_classify(_world(hydrology=wire))
        self.assertIsInstance(result, RiverTypeClassify)
        self.assertEqual(result, WorldHydrology().default_rivers.type_classify)

    def test_partial_policy_preserves_custom_value_and_model_defaults(self):
        raw = {"default_rivers": {"type_classify": {"mountain_min_source_z": 100}}}
        wire = normalize_world({"hydrology": raw})["hydrology"]
        result = resolve_river_type_classify(_world(hydrology=wire))
        self.assertEqual(result, RiverTypeClassify(mountain_min_source_z=100))
        hm = heightmap_from_z({(x, 0): 50 for x in range(3)})
        path = list(hm.surface_z)
        self.assertEqual(classify_river_type(path, hm, resolve_river_type_classify(_world())),
                         HydrologyConnectionType.MOUNTAIN_RIVER)
        self.assertEqual(classify_river_type(path, hm, result), HydrologyConnectionType.RIVER)

    def test_custom_fields_roundtrip_without_runtime_projection(self):
        custom = RiverTypeClassify(mountain_min_source_z=80, path_mountain_fraction=0.75,
            rapid_drop_threshold_m=7, mountain_bed_steepness_factor=2.25, foothill_gradient_threshold=0.3)
        raw = {"default_rivers": {"type_classify": custom.model_dump(mode="json")}}
        wire = normalize_world({"hydrology": raw})["hydrology"]
        result = resolve_river_type_classify(_world(hydrology=wire))
        self.assertEqual(result, custom)
        self.assertEqual(RiverTypeClassify.model_validate_json(result.model_dump_json()), custom)

    def test_invalid_policy_rejects_import_and_runtime_without_local_fallback(self):
        for value in (None, {"mountain_min_source_z": None}, {"path_mountain_fraction": 1.01},
                      {"mountain_bed_steepness_factor": 0}, {"rapid_drop_threshold_m": -1}):
            with self.subTest(value=value):
                raw = {"default_rivers": {"type_classify": value}}
                with self.assertRaises(ImportValidationError):
                    normalize_world({"hydrology": raw})
                with self.assertRaises(UnresolvedModelError):
                    resolve_river_type_classify(_world(hydrology=raw))

    def test_null_fields_do_not_use_schema_defaults(self):
        w = _world(hydrology={"default_rivers": {"type_classify": {
            "mountain_min_source_z": None, "foothill_gradient_threshold": None}}})
        with self.assertRaises(UnresolvedModelError):
            resolve_river_type_classify(w)


class TestGeographicLocations(unittest.TestCase):

    def _loc(self, loc_type: str, subtype: str | None) -> NamedLocation:
        return NamedLocation(
            location_uid="loc-1",
            world_uid="test-world",
            display_name="Test",
            system_location_type=loc_type,
            system_location_subtype=subtype,
            created_at="2026-06-26T00:00:00",
        )

    def test_fixture_shape_matches_geographic_filter(self):
        loc = self._loc("geographic", "lake")
        self.assertTrue(is_geographic_location(loc))
        self.assertEqual(len(geographic_locations([loc])), 1)

    def test_geographic_prefix_on_subtype_does_not_match(self):
        """Docs notation geographic.lake ≠ DB field value — must not filter by prefix."""
        loc = self._loc("geographic", "geographic.lake")
        self.assertTrue(is_geographic_location(loc))
        self.assertEqual(len(geographic_locations([loc])), 1)

    def test_settlement_excluded(self):
        loc = self._loc("settlement", None)
        self.assertFalse(is_geographic_location(loc))

    def test_build_master_input_includes_geographic(self):
        w = _world()
        loc = self._loc("geographic", "sea")
        inp = build_hydrology_master_input(w, [loc], [], [])
        self.assertEqual(len(inp.geographic_locations), 1)
        self.assertEqual(inp.geographic_locations[0].system_location_subtype, "sea")


class TestHydrologyStub(unittest.TestCase):

    def test_disabled_returns_empty(self):
        w = _world(hydrology={"enabled": False})
        svc = HydrologyGeneratorService()
        hm = SurfaceHeightmap(
            world_uid="test-world",
            bbox=GridBBox(0, 0, 0, 0),
            surface_z={},
        )
        result = svc.apply(w, [], hm)
        self.assertEqual(len(result.cell_index.roles), 0)

    def test_is_hydrology_enabled_false(self):
        self.assertFalse(is_hydrology_enabled(_world(hydrology={"enabled": False})))


class TestMapCellHydrology(unittest.TestCase):

    def test_lake_role_sets_liquid_candidate(self):
        from app.dataModel.hydrology import HydrologyCellRole, MapCellHydrology
        from app.dataModel.hydrology.mapCellHydrology import (
            cell_hydrology_liquid_candidate,
            dump_cell_hydrology,
            parse_cell_hydrology,
        )

        pojo = MapCellHydrology(role=HydrologyCellRole.LAKE)
        self.assertTrue(pojo.is_liquid_candidate())
        wire = dump_cell_hydrology(pojo)
        self.assertIsNotNone(wire)
        self.assertTrue(cell_hydrology_liquid_candidate(wire))
        roundtrip = parse_cell_hydrology(wire)
        self.assertIsNotNone(roundtrip)
        assert roundtrip is not None
        self.assertEqual(roundtrip.role, HydrologyCellRole.LAKE)

    def test_shore_role_clears_liquid_candidate(self):
        from app.dataModel.hydrology import MapCellHydrology, HydrologyCellRole

        pojo = MapCellHydrology(role=HydrologyCellRole.SHORE, liquid_candidate=True)
        self.assertFalse(pojo.is_liquid_candidate())


if __name__ == "__main__":
    unittest.main()
