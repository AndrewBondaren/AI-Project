"""Unit tests for hydrology pure helpers — D HY-1."""

import unittest
from types import SimpleNamespace

from app.application.worldData.generators.terrain.hydrology.loadHydrologyFromWorld import (
    is_hydrology_enabled,
)
from app.application.worldData.generators.terrain.hydrology.resolveHydrologyBands import (
    clamp_bands,
    resolve_hydrology_bands,
)
from app.application.worldData.generators.terrain.hydrology.resolveRiverTypeClassify import (
    resolve_river_type_classify,
)
from app.application.worldData.generators.terrain.hydrology.buildHydrologyMasterInput import (
    build_hydrology_master_input,
)
from app.application.worldData.generators.terrain.hydrology.hydrologyLocations import (
    geographic_locations,
    is_geographic_location,
)
from app.application.worldData.generators.terrain.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.db.models.namedLocation import NamedLocation
from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.terrain.types import SurfaceHeightmap


def _world(**kwargs):
    defaults = {
        "world_uid": "test-world",
        "hydrology": {"enabled": True},
        "map_cell_size_m": 3000,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestHydrologyBands(unittest.TestCase):

    def test_clamp_swaps_inverted(self):
        b = clamp_bands(10, 3)
        self.assertEqual(b.min, 3)
        self.assertEqual(b.max, 10)

    def test_resolve_default_rivers_bands(self):
        w = _world(hydrology={
            "enabled": True,
            "default_rivers": {"bands": {"min": 2, "max": 8}},
        })
        b = resolve_hydrology_bands("rivers", w)
        self.assertEqual(b.min, 2)
        self.assertEqual(b.max, 8)


class TestRiverTypeClassify(unittest.TestCase):

    def test_null_fields_use_schema_defaults(self):
        w = _world(hydrology={
            "default_rivers": {
                "type_classify": {
                    "mountain_min_source_z": None,
                    "foothill_gradient_threshold": None,
                },
            },
        })
        tc = resolve_river_type_classify(w)
        self.assertEqual(tc.mountain_min_source_z, 40)
        self.assertAlmostEqual(tc.foothill_gradient_threshold, 0.12)


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
