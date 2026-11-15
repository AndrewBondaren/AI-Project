import json
import unittest
from unittest.mock import patch

from app.application.worldData.pack.encoding.gradeSlotsFormat import (
    GradeSlotsDecoder, GradeSlotsValidationError, GradeSlotsFormatError, grade_slots_format)
from app.application.worldData.pack.encoding.jsonDecodeBudget import JsonDecodeLimitError
from app.application.worldData.pack.encoding.jsonDecodeErrors import JsonDecodeInputError
from app.dataModel.encoding.decodeLimits import DecodeLimits
from app.dataModel.terrain.relief.gradeSlot import GradeSlotSidecar, GradeCellSlots, GRADE_SLOT_SCHEMA_ID
from app.dataModel.worldPack.meta.gradeSlotsStorageFormat import GRADE_SLOTS_STORAGE_VERSION


class GradeSlotsFormatTests(unittest.TestCase):
    def setUp(self):
        self.limits = DecodeLimits(max_bytes=10000, max_nodes=1000, max_depth=10, max_items=100)
        self.decoder = GradeSlotsDecoder(self.limits)
        self.row = dict(x=12, y=-8, slots=list(range(8)))

    def payload(self, cells):
        return json.dumps(dict(schema_id=GRADE_SLOT_SCHEMA_ID, cells=cells)).encode()

    def test_roundtrip_keeps_order_and_exact_bytes(self):
        payload = self.payload([self.row, dict(x=-3, y=4, slots=[10] * 8)])
        result = self.decoder.decode(payload, GRADE_SLOTS_STORAGE_VERSION)
        self.assertEqual([row.cell for row in result.cells], [(12, -8), (-3, 4)])
        self.assertEqual(result.cells[0].slots, tuple(range(8)))
        contract = grade_slots_format(self.limits)
        self.assertIs(contract.encode(payload), payload)
        self.assertIs(contract.decode(payload, GRADE_SLOTS_STORAGE_VERSION), payload)
        self.assertEqual(self.decoder.validate(result), result)

    def test_missing_cells_preserves_default_but_null_is_invalid(self):
        payload = json.dumps(dict(schema_id=GRADE_SLOT_SCHEMA_ID)).encode()
        self.assertEqual(self.decoder.decode(payload, GRADE_SLOTS_STORAGE_VERSION).cells, ())
        self.assertEqual(self.decoder.decode(self.payload([]), GRADE_SLOTS_STORAGE_VERSION).cells, ())
        with self.assertRaises(GradeSlotsValidationError):
            self.decoder.decode(self.payload(None), GRADE_SLOTS_STORAGE_VERSION)

    def test_schema_missing_unknown_extra_and_duplicate_keys(self):
        for payload in (b'{}', b'{"schema_id":"other"}',
                        json.dumps(dict(schema_id=GRADE_SLOT_SCHEMA_ID, extra=1)).encode()):
            with self.subTest(payload=payload), self.assertRaises(GradeSlotsValidationError):
                self.decoder.decode(payload, GRADE_SLOTS_STORAGE_VERSION)
        for payload in (b'{"schema_id":"x","schema_id":"x"}', b'{"cells":[{"x":1,"x":2}]}'):
            with self.assertRaises(JsonDecodeInputError):
                self.decoder.decode(payload, GRADE_SLOTS_STORAGE_VERSION)

    def test_cell_type_range_extra_and_duplicate_errors_aggregate(self):
        rows = [self.row, self.row | {"slots": [True] * 8},
                dict(x="1", y=False, slots=[11] * 8, extra=1)]
        with self.assertRaises(GradeSlotsValidationError) as caught:
            self.decoder.decode(self.payload(rows), GRADE_SLOTS_STORAGE_VERSION)
        issues = caught.exception.issues
        self.assertGreaterEqual(len(issues), 6)
        self.assertTrue(any(issue.code == "VALIDATION_ERROR" for issue in issues))
        self.assertTrue(any(issue.pydantic_type == "extra_forbidden" for issue in issues))

    def test_forged_instances_are_rechecked(self):
        good = GradeCellSlots(x=0, y=0, slots=tuple(range(8)))
        for bad in (good.model_copy(update={"x": True}), good.model_copy(update={"slots": [0] * 8}),
                    good.model_copy(update={"slots": (11,) * 8}), good.model_copy(update={"extra": 1})):
            with self.assertRaises(GradeSlotsValidationError):
                self.decoder.validate(GradeSlotSidecar.model_construct(schema_id=GRADE_SLOT_SCHEMA_ID, cells=(bad,)))

    def test_resource_failure_precedes_json_parser(self):
        decoder = GradeSlotsDecoder(DecodeLimits(max_bytes=10000, max_nodes=2, max_depth=10, max_items=100))
        with patch('app.application.worldData.pack.encoding.gradeSlotsFormat.json.loads') as parser:
            with self.assertRaises(JsonDecodeLimitError):
                decoder.decode(self.payload([self.row]), GRADE_SLOTS_STORAGE_VERSION)
            parser.assert_not_called()
        contract = grade_slots_format(DecodeLimits(max_bytes=1, max_nodes=1, max_depth=1, max_items=1))
        with self.assertRaises(JsonDecodeLimitError):
            contract.encode(self.payload([]))

    def test_syntax_utf8_and_version_have_typed_errors(self):
        for payload in (b'{', b'"\xff"'):
            with self.assertRaises(JsonDecodeInputError):
                self.decoder.decode(payload, GRADE_SLOTS_STORAGE_VERSION)
        with self.assertRaises(GradeSlotsFormatError):
            self.decoder.decode(self.payload([]), GRADE_SLOTS_STORAGE_VERSION + 1)
