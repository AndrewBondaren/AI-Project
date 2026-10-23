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
