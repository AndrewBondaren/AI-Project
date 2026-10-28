"""Actual geometry helpers, projection limits and explicitly supplied seed."""

from unittest import TestCase

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.placement.adapters.water import prepare_authored_water_geometry
from app.application.worldData.generators.hydrology.placement.projectDeclaredHydrology import project_water_source
from app.dataModel.hydrology.declaredBasin import DeclaredBasin
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.waterSide import WaterSide
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.hydrology.sources.waterDesignSource import AuthoredBasinSource, AuthoredLakeSource, CoastlineWaterSource
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY
from app.dataModel.spatial.regionShape import AnchorRadiusShape, BboxShape, EdgeNoise, PolygonShape
from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterAnchorInput
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
from tests.geo1.authored.fixtures import request


def ring():
    return tuple(HydrologyWaypoint(x=x, y=y) for x, y in ((4, 4), (12, 4), (12, 12), (4, 12)))


class AuthoredGeometryTests(TestCase):
    def test_basin_projects_once_without_changing_floor_identity_or_height_snapshot(self):
        req = request()
        before = req.model_dump_json()
        result = prepare_authored_water_geometry(req)
        self.assertEqual(result.footprints, (frozenset((x, y) for y in range(2, 7) for x in range(2, 7)),))
        self.assertEqual(result.source_uid, "source")
        self.assertEqual(result.pre_hydrology_ref, req.pre_hydrology.ref)
        self.assertEqual(result.coordinate_space, CoordinateSpace.WORLD_SURFACE_GRID)
        self.assertIsNone(result.rim_level)
        self.assertEqual(req.model_dump_json(), before)

    def test_ready_fine_anchor_is_projected_for_existing_anchor_radius_helper(self):
        source = AuthoredBasinSource(value=DeclaredBasin(location_uid="anchor-basin", kind=BasinKind.LAKE,
            footprint=AnchorRadiusShape(anchor_uid="anchor", radius=4), floor_z=-5))
        anchor = WaterAnchorInput(source_uid="anchor", position=(FineX(8), FineY(8)), subtype=None)
        result = prepare_authored_water_geometry(request(source, anchors=(anchor,)))
        self.assertIn((4, 4), result.footprints[0])
        self.assertIn((6, 4), result.footprints[0])
        self.assertNotIn((8, 8), result.footprints[0])
        with self.assertRaises(PlanBuildFailure):
            prepare_authored_water_geometry(request(source))

    def test_lake_rim_level_comes_from_actual_coarse_terrain(self):
        result = prepare_authored_water_geometry(request(AuthoredLakeSource(value=DeclaredLake(location_uid="lake", shoreline=ring()))))
        self.assertEqual(result.footprints[0], frozenset((x, y) for y in range(3, 6) for x in range(3, 6)))
        self.assertEqual(result.rim_level, 12)

    def test_degenerate_lake_returns_contour_and_notice(self):
        source = AuthoredLakeSource(value=DeclaredLake(location_uid="line", shoreline=ring()[:2]))
        result = prepare_authored_water_geometry(request(source))
        self.assertTrue(result.footprints[0])
        self.assertTrue(any(n.code == "WATER_PLACEMENT_DEGENERATE_RING" for n in result.notices))

    def test_open_coastline_uses_supplied_caps_without_autoresolve_or_admission(self):
        source = CoastlineWaterSource(value=DeclaredCoastline(location_uid="coast", kind=BasinKind.SEA, path=ring()[:2]))
        req = request(source, seas=HydrologySeasPolicy(enabled=False, autoresolve=False,
            max_area_fraction=0.05, max_extent_x_fraction=1.0, max_extent_y_fraction=1.0))
        result = prepare_authored_water_geometry(req)
        self.assertLessEqual(len(result.footprints[0]), 4)
        self.assertTrue(any(n.code == "WATER_PLACEMENT_CAP_REACHED" for n in result.notices))

    def test_closed_coastline_water_side_uses_existing_ring_geometry(self):
        inside = CoastlineWaterSource(value=DeclaredCoastline(location_uid="closed", kind=BasinKind.SEA,
            path=ring(), closed=True, water_side=WaterSide.INTERIOR))
        outside = CoastlineWaterSource(value=inside.value.model_copy(update={"water_side": WaterSide.EXTERIOR}))
        a = prepare_authored_water_geometry(request(inside)).footprints[0]
        b = prepare_authored_water_geometry(request(outside)).footprints[0]
        self.assertEqual(len(a), 9)
        self.assertTrue(a.isdisjoint(b))

    def test_projection_collapse_is_failure_instead_of_fabricated_geometry(self):
        source = AuthoredBasinSource(value=DeclaredBasin(location_uid="tiny", kind=BasinKind.SEA, floor_z=-5,
            footprint=PolygonShape(vertices=((0, 0), (1, 0), (0, 1)))))
        with self.assertRaises(PlanBuildFailure) as raised:
            prepare_authored_water_geometry(request(source))
        self.assertEqual(raised.exception.issues[0].code, "WATER_PLACEMENT_GEOMETRY")

    def test_planar_geometry_is_not_clipped_and_wrapped_geometry_is_canonical(self):
        source = AuthoredBasinSource(value=DeclaredBasin(location_uid="seam", kind=BasinKind.SEA, floor_z=-5,
            footprint=BboxShape(x_min=-4, x_max=4, y_min=4, y_max=8)))
        with self.assertRaises(PlanBuildFailure):
            prepare_authored_water_geometry(request(source))
        for mode in (Mode.WRAPPED, Mode.SPHERE):
            req = request(source, mode=mode)
            result = prepare_authored_water_geometry(req)
            self.assertTrue(all(req.topology.canonicalize(*c) == c for c in result.footprints[0]))
            self.assertTrue({0, 9} <= {c[0] for c in result.footprints[0]})

    def test_noise_uses_explicit_seed_independently_of_actual_world_identity(self):
        source = AuthoredBasinSource(value=DeclaredBasin(location_uid="noise", kind=BasinKind.SEA, floor_z=-5,
            footprint=BboxShape(x_min=0, x_max=16, y_min=0, y_max=16, edge_noise=EdgeNoise(amplitude=4, scale=6))))
        req = request(source)
        expected = prepare_authored_water_geometry(req)
        ref = req.pre_hydrology.ref
        other_ref = ref.model_copy(update={"key": ref.key.model_copy(update={"world_uid": "other-world"})})
        changed_world = req.model_copy(update={"pre_hydrology": req.pre_hydrology.model_copy(update={"ref": other_ref})})
        self.assertEqual(prepare_authored_water_geometry(changed_world).footprints, expected.footprints)
        self.assertNotEqual(prepare_authored_water_geometry(req.model_copy(update={"seed_root": "other-seed"})).footprints, expected.footprints)

    def test_single_source_projection_retains_waypoint_z_and_source_fields(self):
        lake = DeclaredLake(location_uid="lake", liquid="water", shoreline=(HydrologyWaypoint(x=-3, y=5, z=7),))
        projected = project_water_source(lake, 2)
        self.assertEqual(projected.location_uid, lake.location_uid)
        self.assertEqual((projected.shoreline[0].x, projected.shoreline[0].y, projected.shoreline[0].z), (-2, 2, 7))
