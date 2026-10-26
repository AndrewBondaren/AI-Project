"""HY-12/4: strict post-carve fill, components, classification and dry shore."""

import unittest

from app.application.worldData.generators.hydrology.water.componentLabel import component_label
from app.application.worldData.generators.hydrology.water.levelFill import LevelFill, level_fill
from app.application.worldData.generators.hydrology.water.shoreDerive import derive_shore
from app.application.worldData.generators.hydrology.water.waterClassifier import classify_components
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from tests.hydrology_fixtures import flat_heightmap, hydro_topology


class LevelFillTests(unittest.TestCase):
    def test_waterline_is_dry_and_elevation_is_unchanged(self):
        hm = flat_heightmap(0, 4, 0, 4, z=0)
        hm.surface_z.update({(1, 2): -3, (2, 2): -2, (3, 2): 0})
        before = dict(hm.surface_z)
        result = level_fill(hm.surface_z, [(1, 2)], 0, hydro_topology(hm))
        self.assertEqual(result.cells, {(1, 2), (2, 2)})
        self.assertEqual((result.area, result.floor_z), (2, -3))
        self.assertEqual(hm.surface_z, before)

    def test_component_and_fill_cross_wrapped_seam(self):
        hm = flat_heightmap(0, 5, 0, 3, z=10)
        hm.surface_z.update({(0, 1): -1, (5, 1): -2})
        topology = hydro_topology(hm, WorldTopologyMode.WRAPPED)
        result = level_fill(hm.surface_z, [(0, 1)], 0, topology)
        self.assertEqual(result.cells, {(0, 1), (5, 1)})
        self.assertEqual(component_label(result.cells, topology), (result.cells,))

    def test_component_and_fill_cross_sphere_fold(self):
        hm = flat_heightmap(0, 5, 0, 3, z=10)
        hm.surface_z.update({(0, 0): -1, (3, 0): -2})
        topology = hydro_topology(hm, WorldTopologyMode.SPHERE)
        result = level_fill(hm.surface_z, [(0, 0)], 0, topology)
        self.assertEqual(result.cells, {(0, 0), (3, 0)})
        self.assertEqual(component_label(result.cells, topology), (result.cells,))

    def test_loaded_bbox_edge_is_not_a_physical_rim(self):
        hm = flat_heightmap(0, 5, 0, 3, z=-1)
        topology = hydro_topology(hm)
        del hm.surface_z[(4, 1)]
        with self.assertRaisesRegex(ValueError, "missing rim elevation"):
            level_fill(hm.surface_z, [(0, 0)], 0, topology)

    def test_components_are_deterministic_and_not_diagonally_connected(self):
        hm = flat_heightmap(0, 3, 0, 3)
        topology = hydro_topology(hm)
        cells = [(2, 2), (0, 0), (1, 0)]
        expected = (frozenset({(0, 0), (1, 0)}), frozenset({(2, 2)}))
        self.assertEqual(component_label(cells, topology), expected)
        self.assertEqual(component_label(reversed(cells), topology), expected)

    def test_shore_is_dry_and_carries_body_level(self):
        hm = flat_heightmap(0, 4, 0, 4, z=0)
        hm.surface_z[(2, 2)] = -3
        before = dict(hm.surface_z)
        water = {(2, 2): MapCellHydrology(role=HydrologyCellRole.LAKE,
                                         water_body_uid="lake-a", z_water_level=0)}
        shore = derive_shore(hm.surface_z, water, hydro_topology(hm))
        self.assertEqual(set(shore), {(1, 2), (3, 2), (2, 1), (2, 3)})
        self.assertTrue(all(entry.role is HydrologyCellRole.SHORE and
                            not entry.liquid_candidate and entry.z_water_level == 0 and
                            entry.water_body_uid == "lake-a" for entry in shore.values()))
        self.assertEqual(hm.surface_z, before)

    def test_compact_ocean_uses_default_level_not_largest_mountain_lake(self):
        hm = flat_heightmap(0, 9, 0, 9)
        topology = hydro_topology(hm, WorldTopologyMode.WRAPPED)
        components = [LevelFill(frozenset({(0, 0), (9, 0)}), -5),
                      LevelFill(frozenset({(x, 5) for x in range(8)}), 90)]
        result = classify_components(components, [0, 100], topology, 0,
                                     HydrologySeasPolicy(), [None, None])
        self.assertEqual(result, (BasinKind.OCEAN, BasinKind.INLAND_SEA))

    def test_authored_kind_survives_procedural_size_threshold(self):
        hm = flat_heightmap(0, 9, 0, 9)
        result = classify_components([LevelFill(frozenset(hm.surface_z), -5)], [0],
                                     hydro_topology(hm), 0, HydrologySeasPolicy(),
                                     [BasinKind.LAKE])
        self.assertEqual(result, (BasinKind.LAKE,))


if __name__ == "__main__":
    unittest.main()
