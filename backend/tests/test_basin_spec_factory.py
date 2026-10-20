"""HY-12 step 3a: basinSpecFactory maps resolved water records to BasinSpec."""

import unittest

from app.application.worldData.generators.hydrology.basinSpecFactory import basin_specs
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from tests.test_water_placement_adapter import basin, coast, context, lake, prepare, resolve


class BasinSpecFactoryTests(unittest.TestCase):
    def test_basin_rim_overrides_and_floor_comes_from_entry(self):
        snap = context()
        prep = prepare(basins=[basin(rim={"min": 2, "max": 9})], snapshot=snap)
        _, records = resolve(prep, snap)
        specs = basin_specs(prep, records, WorldHydrology())
        self.assertEqual(len(specs), 1)
        result = specs[0]
        self.assertEqual((result.bands.min, result.bands.max), (2, 9))
        self.assertEqual(result.floor_z, -20)
        self.assertEqual(result.footprint, records[0].footprint_cells)
        self.assertEqual(result.kind, BasinKind.OCEAN)

    def test_basin_without_rim_uses_seas_bands(self):
        snap = context()
        prep = prepare(basins=[basin()], snapshot=snap)
        _, records = resolve(prep, snap)
        result = basin_specs(prep, records, WorldHydrology())[0]
        defaults = WorldHydrology().default_seas.bands
        self.assertEqual((result.bands.min, result.bands.max), (defaults.min, defaults.max))

    def test_lake_uses_lakes_bands_and_policy_floor(self):
        snap = context(auto={"lake": 1})
        prep = prepare(lakes=[lake()], snapshot=snap)
        _, records = resolve(prep, snap)
        result = basin_specs(prep, records, WorldHydrology())[0]
        defaults = WorldHydrology().default_lakes
        self.assertEqual((result.bands.min, result.bands.max),
                         (defaults.bands.min, defaults.bands.max))
        self.assertEqual(result.floor_z, records[0].z_water_level - defaults.basin_depth)
        self.assertEqual(result.kind, BasinKind.LAKE)

    def test_coastline_uses_seas_bands_and_policy_floor(self):
        snap = context()
        prep = prepare(coasts=[coast()], snapshot=snap)
        _, records = resolve(prep, snap)
        result = basin_specs(prep, records, WorldHydrology())[0]
        defaults = WorldHydrology().default_seas
        self.assertEqual((result.bands.min, result.bands.max),
                         (defaults.bands.min, defaults.bands.max))
        self.assertEqual(result.floor_z, records[0].z_water_level - defaults.basin_depth)

    def test_record_without_prepared_entry_is_an_error(self):
        snap = context()
        prep = prepare(basins=[basin()], snapshot=snap)
        _, records = resolve(prepare(basins=[basin("other")], snapshot=snap), snap)
        with self.assertRaises(ValueError):
            basin_specs(prep, records, WorldHydrology())


if __name__ == "__main__":
    unittest.main()
