from copy import replace
from unittest import TestCase

from pydantic import ValidationError

from app.dataModel.placement.common import AbsoluteMovement
from app.dataModel.placement.prepared import CapturedPlacementGeometry
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from tests.geo1.contracts.test_placement_lifecycle import member, prepared, variant
from tests.geo1.fine_water.test_fill import source


class CapturedGeometryTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref = source(hills=False)[0].ref
        owner = prepared(member("competitor"))
        cls.args = dict(coordinate_space=CoordinateSpace.WORLD_FINE_GRID, pre_hydrology_ref=cls.ref,
                        intent=owner.intent, candidates=owner.candidates, original_area=1)

    def test_overlapping_alternatives_keep_original_area_and_order(self):
        candidates = (variant("b", ((1, 0), (2, 0))), variant("a", ((0, 0), (1, 0))))
        intent = replace(self.args["intent"], absolute_movement=AbsoluteMovement.EXPLICIT_CANDIDATES)
        record = CapturedPlacementGeometry(**(self.args | dict(candidates=candidates, intent=intent, original_area=3)))
        self.assertEqual(record.original_area, 3.0)
        self.assertEqual(record.candidates, candidates)
        self.assertEqual(record.pre_hydrology_ref, self.ref)
        self.assertEqual(CapturedPlacementGeometry.model_validate(record), record)
        with self.assertRaises(ValidationError):
            record.original_area = 4

    def test_exact_area_before_float_conversion(self):
        self.assertEqual(CapturedPlacementGeometry(**(self.args | dict(original_area=2**53))).original_area, 2**53)
        for value in (True, "1", 0, -1, 1.25, float("nan"), float("inf"), 2**53 + 1):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                CapturedPlacementGeometry(**(self.args | dict(original_area=value)))

    def test_required_fields_frame_and_candidate_policy(self):
        for name in self.args:
            with self.subTest(missing=name), self.assertRaises(ValidationError):
                CapturedPlacementGeometry(**{k: v for k, v in self.args.items() if k != name})
        record = CapturedPlacementGeometry(**self.args)
        other_ref = replace(self.ref, key=replace(self.ref.key, world_uid="other"))
        for changes in (dict(coordinate_space="world_fine_grid"), dict(coordinate_space=CoordinateSpace.WORLD_SURFACE_GRID),
                        dict(original_area=2**53 + 1), dict(pre_hydrology_ref=other_ref), dict(candidates=()),
                        dict(candidates=record.candidates * 2),
                        dict(candidates=(*record.candidates, variant("alt", ((1, 0),))))):
            with self.subTest(changes=changes.keys()), self.assertRaises(ValidationError):
                CapturedPlacementGeometry.model_validate(record.model_copy(update=changes))
