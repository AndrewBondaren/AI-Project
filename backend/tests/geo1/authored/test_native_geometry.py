from copy import replace
from unittest import TestCase

from pydantic import ValidationError

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.placement.adapters.water import prepare_authored_water_geometry
from app.application.worldData.placement.adapters.waterGeometry.nativeGeometry import prepare_native_water_geometry
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.waterSide import WaterSide
from app.dataModel.hydrology.sources.waterDesignSource import AuthoredLakeSource, CoastlineWaterSource
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.regionShape import AnchorRadiusShape, BboxShape
from app.dataModel.terrain.designedWater.geometry.authoredGeometry import AuthoredWaterGeometryRequest
from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterAnchorInput
from tests.geo1.authored.fixtures import request
from tests.geo1.authored.test_geometry import ring
from tests.geo1.fine_water.fixtures import physical_inputs
from tests.geo1.fine_water.test_fill import source
from tests.geo1.hill_hosts.test_hosts import coverage


class NativeAuthoredGeometryTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.window, _, topology = source(hills=False)
        physical = physical_inputs(topology)
        legacy = request()
        cls.args = dict(source=legacy.source, pre_hydrology=cls.window, topology=topology,
                        grid=physical.grid, seed_root=legacy.seed_root, anchors=(),
                        seas=legacy.seas, z_min=physical.z_min)

    def geometry(self, **changes):
        return prepare_native_water_geometry(AuthoredWaterGeometryRequest(**(self.args | changes)))

    def test_exact_subcell_basin_and_anchor(self):
        basin = self.args["source"]
        shape = BboxShape(x_min=3, x_max=4, y_min=5, y_max=5)
        result = self.geometry(source=replace(basin, value=replace(basin.value, footprint=shape)))
        self.assertEqual(result.footprints, (frozenset({(3, 5), (4, 5)}),))
        self.assertIs(result.coordinate_space, CoordinateSpace.WORLD_FINE_GRID)
        self.assertEqual(result.pre_hydrology_ref, self.window.ref)
        anchor = WaterAnchorInput(source_uid="port", position=(9, 7), subtype=None)
        anchored = replace(basin, value=replace(basin.value, footprint=AnchorRadiusShape(anchor_uid="port", radius=1)))
        self.assertIn((10, 7), self.geometry(source=anchored, anchors=(anchor,)).footprints[0])
        with self.assertRaises(PlanBuildFailure):
            self.geometry(source=anchored)

    def test_lake_uses_only_observed_fine_rim(self):
        lake = AuthoredLakeSource(value=DeclaredLake(location_uid="lake", shoreline=ring()))
        result = self.geometry(source=lake)
        self.assertEqual(result.footprints, (frozenset((x, y) for y in range(5, 12) for x in range(5, 12)),))
        heights = dict(self.window.payload.surface_z)
        rim = {(a, b) for a in range(5, 12) for b in (4, 12)}
        self.assertEqual(result.rim_level, max(heights[c] for c in rim | {(y, x) for x, y in rim}))
        line = replace(lake, value=replace(lake.value, shoreline=ring()[:2]))
        self.assertEqual(self.geometry(source=line).notices[0].code, "WATER_PLACEMENT_DEGENERATE_RING")

    def test_coastline_interior_and_open_cap(self):
        coast = CoastlineWaterSource(value=DeclaredCoastline(location_uid="coast", kind=BasinKind.SEA,
            path=ring(), closed=True, water_side=WaterSide.INTERIOR))
        self.assertEqual(self.geometry(source=coast).footprints[0],
                         frozenset((x, y) for y in range(5, 12) for x in range(5, 12)))
        line = CoastlineWaterSource(value=DeclaredCoastline(location_uid="line", kind=BasinKind.SEA, path=ring()[:2]))
        capped = self.geometry(source=line, seas=replace(self.args["seas"], max_area_fraction=0.04))
        self.assertLessEqual(len(capped.footprints[0]), 40)
        self.assertEqual(capped.notices[0].code, "WATER_PLACEMENT_CAP_REACHED")

    def test_rejects_partial_window_wrong_frame_and_coarse_request(self):
        partial = source(cells=coverage(0, 1, 0, 1), hills=False)[0]
        for change in (dict(pre_hydrology=partial), dict(topology=request().topology),
                       dict(anchors=(WaterAnchorInput(source_uid="bad", position=(32, 0), subtype=None),))):
            with self.subTest(fields=tuple(change)), self.assertRaises(ValidationError):
                self.geometry(**change)
        with self.assertRaises(TypeError):
            prepare_native_water_geometry(request())
        with self.assertRaises(TypeError):
            prepare_authored_water_geometry(AuthoredWaterGeometryRequest(**self.args))
