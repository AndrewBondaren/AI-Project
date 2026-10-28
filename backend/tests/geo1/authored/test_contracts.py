"""Immutable request/result records and strict geometry boundary admission."""

from unittest import TestCase

from pydantic import ValidationError

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.placement.adapters.water import prepare_authored_water_geometry
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.terrain.designedWater.geometry.authoredGeometry import AuthoredWaterGeometry, AuthoredWaterGeometryRequest
from app.dataModel.validation.immutableValue import validate_immutable
from tests.geo1.authored.fixtures import request


class AuthoredGeometryContractTests(TestCase):
    def test_request_and_result_are_immutable_and_roundtrippable(self):
        req = request()
        result = prepare_authored_water_geometry(req)
        for value in (req, result):
            validate_immutable(value)
            self.assertEqual(type(value).model_validate_json(value.model_dump_json()), value)
            with self.assertRaises(ValidationError):
                value.z_min = -99

    def test_actual_terrain_bounds_and_z_min_are_checked(self):
        req = request()
        for update in ({"z_min": 11}, {"z_min": True},
                       {"topology": req.topology.model_copy(update={"bounds": req.topology.bounds.model_copy(update={"x_max": 10})})}):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                AuthoredWaterGeometryRequest.model_validate(req.model_copy(update=update))

    def test_copied_seas_limits_are_revalidated_without_fallback_defaults(self):
        req = request()
        for value in (0.0, -1.0, 1.1, float("nan"), True, "bad"):
            seas = req.seas.model_copy(update={"max_area_fraction": value})
            with self.subTest(value=value), self.assertRaises((ValidationError, ValueError)):
                AuthoredWaterGeometryRequest.model_validate(req.model_copy(update={"seas": seas}))
        with self.assertRaises(PlanBuildFailure):
            prepare_authored_water_geometry(req.model_copy(update={"seas": HydrologySeasPolicy().model_copy(update={"max_area_fraction": 0.0})}))

    def test_raw_request_cannot_enter_application_boundary(self):
        with self.assertRaises(TypeError):
            prepare_authored_water_geometry(request().model_dump())

    def test_empty_or_local_geometry_is_not_a_valid_result(self):
        from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
        geometry = prepare_authored_water_geometry(request())
        for update in ({"footprints": ()}, {"footprints": (frozenset(),)}, {"coordinate_space": CoordinateSpace.LOCATION_FINE_GRID}):
            with self.assertRaises(ValidationError):
                AuthoredWaterGeometry.model_validate(geometry.model_copy(update=update))
