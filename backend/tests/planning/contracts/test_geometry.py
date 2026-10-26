"""Shared value contracts retain legacy validation and symbol identity."""

import math
from dataclasses import FrozenInstanceError, fields
from unittest import TestCase

from pydantic import TypeAdapter, ValidationError

from app.dataModel.identity import EntityUid as PublicEntityUid
from app.dataModel.identity.uid import EntityUid
from app.dataModel.placement.common import PlacementUid
from app.dataModel.placement.intent import PlacementIdentity


class EntityUidTests(TestCase):
    def test_legacy_and_public_imports_share_the_same_type(self):
        self.assertIs(PlacementUid, EntityUid)
        self.assertIs(PublicEntityUid, EntityUid)

    def test_valid_authored_uids_round_trip_without_changes(self):
        adapter = TypeAdapter(EntityUid)
        for value in ("x", "world-test-004", "loc:гора/1", "authored uid"):
            with self.subTest(value=value):
                self.assertEqual(adapter.validate_python(value), value)
                self.assertEqual(adapter.validate_json(adapter.dump_json(value)), value)

    def test_empty_padded_and_non_string_values_are_rejected(self):
        adapter = TypeAdapter(EntityUid)
        for value in ("", " ", "\t", " uid", "uid ", "\tuid", "uid\n", "\u00a0uid",
                      None, 1, 1.5, True, b"uid", [], {}):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    adapter.validate_python(value)

    def test_placement_identity_preserves_wire_values(self):
        payload = {"world_uid": "world", "source_uid": "source", "region_uid": "region"}
        identity = PlacementIdentity.model_validate(payload)
        self.assertEqual(identity.model_dump(mode="json"), payload)
        self.assertEqual(PlacementIdentity.model_validate_json(identity.model_dump_json()), identity)

    def test_legacy_placement_fields_keep_strict_validation(self):
        payload = {"world_uid": "world", "source_uid": "source", "region_uid": "region"}
        for field in payload:
            for value in ("", " padded", 1, True):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValidationError):
                        PlacementIdentity.model_validate({**payload, field: value})


class GridBBoxTests(TestCase):
    def test_old_and_new_imports_share_the_same_class(self):
        from app.dataModel.spatial.grid import GridBBox as PublicGridBBox
        from app.dataModel.spatial.grid.gridBBox import GridBBox
        from app.application.worldData.generators.climate.climatePoleField import GridBBox as ClimateGridBBox
        from app.application.worldData.generators.terrain.types import GridBBox as TerrainGridBBox

        self.assertIs(PublicGridBBox, GridBBox)
        self.assertIs(ClimateGridBBox, GridBBox)
        self.assertIs(TerrainGridBBox, GridBBox)

    def test_fields_constructor_and_frozen_semantics_are_preserved(self):
        from app.dataModel.spatial.grid.gridBBox import GridBBox

        self.assertEqual([field.name for field in fields(GridBBox)],
                         ["x_min", "x_max", "y_min", "y_max"])
        bbox = GridBBox(-2, 3, -4, 5)
        self.assertEqual(bbox, GridBBox(x_min=-2, x_max=3, y_min=-4, y_max=5))
        with self.assertRaises(FrozenInstanceError):
            setattr(bbox, "x_min", 0)

    def test_diagonal_retains_legacy_axis_clamp(self):
        from app.dataModel.spatial.grid.gridBBox import GridBBox

        for bbox, expected in ((GridBBox(0, 3, 0, 4), 5.0),
                               (GridBBox(2, 2, -3, -3), math.sqrt(2)),
                               (GridBBox(0, 0, 0, 4), math.sqrt(17))):
            with self.subTest(bbox=bbox):
                self.assertAlmostEqual(bbox.diagonal(), expected)

    def test_coordinate_consumers_keep_inclusive_bounds(self):
        from app.application.worldData.generators.coordinates.worldTile import (
            fine_bbox_for_tile, iter_macro_tiles, macro_bbox_to_fine_bbox,
        )
        from app.dataModel.spatial.grid.gridBBox import GridBBox

        macro = GridBBox(-1, 0, 2, 2)
        self.assertEqual(list(iter_macro_tiles(macro)), [(-1, 2), (0, 2)])
        self.assertEqual(fine_bbox_for_tile(-1, 2, 4), GridBBox(-4, -1, 8, 11))
        self.assertEqual(macro_bbox_to_fine_bbox(macro, 4), GridBBox(-4, 3, 8, 11))


class CoordinateValueTests(TestCase):
    def test_light_scale_and_all_coordinate_aliases_share_canonical_objects(self):
        from app.application.worldData.pack.bake.lightGrid import coords as legacy
        from app.application.worldData.generators.coordinates.light import grid
        from app.dataModel.spatial.grid import lightGridScale as scale
        from app.dataModel.worldPack.wire.worldMapCellsPerTile import light_span_for

        for name in ("LightGridScale", "light_span_for"):
            self.assertIs(getattr(legacy, name), getattr(scale, name))
        self.assertIs(light_span_for, scale.light_span_for)
        for name in ("fine_to_light", "light_to_macro_local", "light_cell_origin_fine",
                     "light_cell_center_fine", "fine_to_macro_local"):
            self.assertIs(getattr(legacy, name), getattr(grid, name))

    def test_light_geometry_retains_negative_boundaries_and_nondivisible_span(self):
        from app.application.worldData.generators.coordinates.light import grid
        from app.dataModel.spatial.grid.lightGridScale import LightGridScale, light_span_for

        scale = LightGridScale.from_tile(1000, 32)
        self.assertEqual(scale.light_span, 31)
        self.assertEqual(light_span_for(0, 0), 1)
        self.assertEqual(LightGridScale.from_tile(0, 0), LightGridScale(1, 1, 1))
        for fine, light, macro in ((-993, -33, (-2, 31)), (-992, -32, (-1, 0)),
                                   (-1, -1, (-1, 31)), (0, 0, (0, 0)),
                                   (991, 31, (0, 31)), (992, 32, (1, 0))):
            with self.subTest(fine=fine):
                self.assertEqual(grid.fine_to_light(fine, fine, scale), (light, light))
                self.assertEqual(grid.light_to_macro_local(light, light, scale),
                                 (macro[0], macro[0], macro[1], macro[1]))
                self.assertEqual(grid.fine_to_macro_local(fine, fine, scale),
                                 (macro[0], macro[0], macro[1], macro[1]))
        self.assertEqual(grid.light_cell_origin_fine(-1, 2, 31, 0, scale), (-39, 2000))
        self.assertEqual(grid.light_cell_center_fine(-1, 2, 31, 0, scale), (-24, 2015))

    def test_coordinate_symbols_are_shared_by_all_import_paths(self):
        from app.application.worldData.generators import coordinates as legacy
        from app.application.worldData.generators.coordinates import types as legacy_types
        from app.dataModel.spatial import grid
        from app.dataModel.spatial.grid import coordinateTypes as shared

        for name in ("GridX", "GridY", "FineX", "FineY", "FineZ", "FineDelta",
                     "SurfaceGridCoord", "FineGridCoord", "SurfaceGridRect", "FineGridRect"):
            with self.subTest(symbol=name):
                self.assertIs(getattr(legacy, name), getattr(shared, name))
                self.assertIs(getattr(legacy_types, name), getattr(shared, name))
                self.assertIs(getattr(grid, name), getattr(shared, name))
        self.assertIs(legacy_types.FineXY, shared.FineXY)
        self.assertIs(grid.FineXY, shared.FineXY)

    def test_newtypes_retain_distinct_units_and_integer_values(self):
        from app.dataModel.spatial.grid import coordinateTypes as shared

        types = [shared.GridX, shared.GridY, shared.FineX, shared.FineY, shared.FineZ, shared.FineDelta]
        self.assertEqual(len(set(types)), len(types))
        for scalar in types:
            with self.subTest(scalar=scalar):
                self.assertIs(scalar.__supertype__, int)
                self.assertEqual(scalar(-3), -3)

    def test_coordinate_space_keeps_legacy_wire_values(self):
        from app.application.worldData.generators.coordinates import CoordinateSpace as LegacySpace
        from app.application.worldData.generators.coordinates.space import CoordinateSpace as LegacyModuleSpace
        from app.dataModel.spatial.grid import CoordinateSpace

        self.assertIs(LegacySpace, CoordinateSpace)
        self.assertIs(LegacyModuleSpace, CoordinateSpace)
        self.assertEqual({item.name: item.value for item in CoordinateSpace}, {
            "WORLD_SURFACE_GRID": "world_surface_grid",
            "WORLD_FINE_GRID": "world_fine_grid",
            "LOCATION_FINE_GRID": "location_fine_grid",
        })

    def test_rectangles_retain_half_open_boundaries(self):
        from app.application.worldData.generators.coordinates.rect import (
            cell_in_fine_rect, cell_in_surface_grid_rect,
        )
        from app.dataModel.spatial.grid import FineGridRect, FineX, FineY, FineZ, GridX, GridY, SurfaceGridRect

        surface = SurfaceGridRect(GridX(-2), GridY(1), GridX(0), GridY(3))
        fine = FineGridRect(FineX(-2), FineY(1), FineX(0), FineY(3), FineZ(7))
        self.assertEqual(surface.as_tuple(), (-2, 1, 0, 3))
        self.assertEqual(fine.as_tuple(), (-2, 1, 0, 3, 7))
        for x, y, expected in ((-2, 1, True), (-1, 2, True), (0, 2, False),
                               (-1, 3, False), (-3, 1, False)):
            with self.subTest(x=x, y=y):
                self.assertEqual(cell_in_surface_grid_rect(x, y, surface), expected)
                self.assertEqual(cell_in_fine_rect(x, y, fine), expected)

    def test_existing_conversion_helpers_accept_shared_records(self):
        from app.application.worldData.generators.coordinates.convert import (
            coarse_cell_fine_xy, fine_to_grid_xy, grid_tile_origin_x,
        )
        from app.dataModel.spatial.grid import FineGridCoord, FineX, FineY, FineZ

        self.assertEqual(fine_to_grid_xy(-1, -9, 8), (-1, -2))
        self.assertEqual(grid_tile_origin_x(-1, 8), -8)
        self.assertEqual(coarse_cell_fine_xy(FineGridCoord(FineX(-4), FineY(6), FineZ(0)),
                                             -1, 2, 8), (-12, 22))

    def test_light_cell_reference_keeps_mask_compatibility(self):
        from app.application.worldData.masks.footprint import LightCellRef as LegacyLightCellRef, MaskFootprint
        from app.dataModel.spatial.grid import LightCellRef

        self.assertIs(LegacyLightCellRef, LightCellRef)
        cell = LightCellRef(-1, 2, 3, 0)
        self.assertEqual(cell.as_absolute(4), (-1, 8))
        footprint = MaskFootprint(frozenset({cell}), elevation_fraction={cell: 0.5})
        self.assertEqual(footprint.elevation_fraction[LegacyLightCellRef(-1, 2, 3, 0)], 0.5)
        with self.assertRaises(FrozenInstanceError):
            setattr(cell, "tx", 1)
