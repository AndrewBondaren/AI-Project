"""Declared hydrology (fine cells) → coarse pass on WORLD_SURFACE_GRID."""

import unittest
from types import SimpleNamespace

from app.application.worldData.generators.coordinates.space import CoordinateSpace
from app.application.worldData.generators.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.hydrology.load.buildHydrologyMasterInput import (
    build_hydrology_master_input,
)
from app.application.worldData.generators.hydrology.load.loadDeclaredHydrology import (
    load_declared_hydrology,
)
from app.application.worldData.generators.hydrology.load.resolveRiverTypeClassify import (
    resolve_river_type_classify,
)
from app.application.worldData.generators.hydrology.rivers.resolveDeclaredRiverPath import (
    resolve_declared_river_intents,
)
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.application.worldData.generators.hydrology.types import HydrologyScope
from tests.hydrology_fixtures import (
    flat_heightmap,
    carve_then_fill,
    hydro_world,
    lake_wire,
    river_endpoints_wire,
    river_segments_wire,
    waypoint,
)

FINE_PER_CELL = 1000


def _world(hydrology: dict) -> SimpleNamespace:
    return hydro_world(
        hydrology={"enabled": True, **hydrology},
        fine_cells_per_map_cell=FINE_PER_CELL,
    )


def _flat_heightmap(x_hi: int, y_hi: int, z: int = 5):
    return flat_heightmap(0, x_hi, 0, y_hi, z=z)


LAKE = lake_wire()
RIVER_SEGMENTS = river_segments_wire()
RIVER_ENDPOINTS = river_endpoints_wire()


class TestCoarseMasterInput(unittest.TestCase):

    def test_lake_and_river_edges_on_surface_grid(self):
        w = _world({"declared_lakes": [LAKE], "declared_rivers": [RIVER_SEGMENTS]})
        inp = build_hydrology_master_input(w, [])
        shore_pts = {p for seg in inp.declared_lake_specs[0].shoreline_segments for p in seg}
        self.assertEqual(shore_pts, {(3, 3), (7, 3), (7, 7), (3, 7)})
        self.assertEqual(inp.declared_river_edges[0].segment, ((1, 9), (5, 9)))

    def test_apply_on_coarse_heightmap_with_declared_lake(self):
        w = _world({"declared_lakes": [LAKE]})
        hm = _flat_heightmap(10, 10)
        result, before_fill = carve_then_fill(w, hm, scopes=frozenset({HydrologyScope.LAKES}))
        self.assertGreater(result.cells_modified, 0)
        self.assertTrue(set(result.cell_index.by_cell) <= set(hm.surface_z))
        self.assertEqual(hm.surface_z, before_fill)

    def test_river_into_lake_keeps_lake_cells(self):
        # Declared lakes are carved/role'd by the pre-1.4 placement pass (HY-12/3b);
        # the legacy apply path emits no LAKE cells for them anymore.
        river_into_lake = {
            **RIVER_ENDPOINTS,
            "source": waypoint(9000, 9000),
            "mouth": waypoint(5000, 5000),
        }
        lake_only = HydrologyGeneratorService().apply(
            _world({"declared_lakes": [LAKE]}), [], _flat_heightmap(10, 10),
        )
        with_river = HydrologyGeneratorService().apply(
            _world({"declared_lakes": [LAKE], "declared_rivers": [river_into_lake]}),
            [],
            _flat_heightmap(10, 10),
        )

        def cells(result, role):
            return {c for c, e in result.cell_index.by_cell.items() if e.role == role}

        self.assertFalse(cells(lake_only, HydrologyCellRole.LAKE))
        self.assertEqual(cells(with_river, HydrologyCellRole.LAKE), cells(lake_only, HydrologyCellRole.LAKE))
        self.assertTrue(cells(with_river, HydrologyCellRole.RIVER_BED))


class TestRiverIntentSpace(unittest.TestCase):

    def _resolve(self, space: CoordinateSpace, hm: SurfaceHeightmap):
        w = _world({"declared_rivers": [RIVER_ENDPOINTS]})
        intents = load_declared_hydrology(w, []).river_intents
        return resolve_declared_river_intents(
            w, hm, intents, [], {}, resolve_river_type_classify(w), space=space,
        )

    def test_endpoints_projected_to_surface_grid(self):
        segments = self._resolve(CoordinateSpace.WORLD_SURFACE_GRID, _flat_heightmap(10, 10))
        cells = segments[0].polyline_cells
        self.assertEqual((cells[0], cells[-1]), ((2, 2), (6, 2)))

    def test_endpoints_kept_on_fine_grid(self):
        segments = self._resolve(CoordinateSpace.WORLD_FINE_GRID, _flat_heightmap(1, 1))
        cells = segments[0].polyline_cells
        self.assertEqual((cells[0], cells[-1]), ((2000, 2000), (6000, 2000)))


if __name__ == "__main__":
    unittest.main()
