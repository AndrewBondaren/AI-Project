import json
import unittest
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.application.worldData.pack.encoding.gradeSlotsFormat import (
    GradeSlotsDecoder, GradeSlotsValidationError, GradeSlotsFormatError, grade_slots_format)
from app.application.worldData.pack.encoding.jsonDecodeBudget import JsonDecodeLimitError
from app.application.worldData.pack.encoding.jsonDecodeErrors import JsonDecodeInputError
from app.dataModel.encoding.decodeLimits import DecodeLimits
from app.dataModel.terrain.relief.gradeSlot import GradeSlotSidecar, GradeCellSlots, GRADE_SLOT_SCHEMA_ID
from app.dataModel.worldPack.meta.gradeSlotsStorageFormat import GRADE_SLOTS_STORAGE_VERSION


class GradeSlotsStorageTests(unittest.TestCase):
    def test_registered_format_stages_reopens_and_refuses_before_reservation(self):
        from tests.snapshotCore.support.fixtures import run_async
        run_async(self._check_registered_storage())

    async def _check_registered_storage(self):
        from app.core.container.packs import PacksWiring
        from app.application.artifacts.staging.artifactStaging import TypedArtifactStager
        from tests.snapshotCore.storage.artifacts.test_staging import SqliteBlobFixture
        from tests.snapshotCore.support.fixtures import live_database
        temporary_root = Path(__file__).resolve().parents[1] / ".tmp_snapshot_core"
        temporary_root.mkdir(exist_ok=True)
        directory = Path(self.enterContext(TemporaryDirectory(dir=temporary_root)))
        database = str(directory / "pack.db")
        payload = json.dumps(dict(schema_id=GRADE_SLOT_SCHEMA_ID, cells=[])).encode()
        limits = DecodeLimits(max_bytes=len(payload), max_nodes=10, max_depth=2, max_items=8)
        async with live_database(database) as bundle:
            fixture = SqliteBlobFixture(bundle)
            registry = fixture.service._registry
            backend = PacksWiring.register_grade_slots_format(registry, directory / "artifacts", fixture.leases, limits=limits)
            self.assertIs(registry.resolve(backend.contract), backend)
            stager = TypedArtifactStager(backend.contract, GRADE_SLOTS_STORAGE_VERSION, registry, fixture.service)
            lease = await fixture.open("grade")
            ref = await stager.stage(lease, payload)
            self.assertEqual(ref.content_hash, hashlib.sha256(payload).hexdigest())
            with patch.object(fixture.service, "reserve", side_effect=AssertionError("unexpected reservation")):
                with self.assertRaises(JsonDecodeLimitError):
                    await stager.stage(lease, payload + b' ')
                with self.assertRaises(GradeSlotsValidationError):
                    await stager.stage(lease, b'{}')
                with self.assertRaises(JsonDecodeInputError):
                    await stager.stage(lease, b'{')
            await fixture.service.finish_preparation(lease, (ref,))
        async with live_database(database, seed=False) as bundle:
            fixture = SqliteBlobFixture(bundle)
            registry = fixture.service._registry
            backend = PacksWiring.register_grade_slots_format(registry, directory / "artifacts", fixture.leases, limits=limits)
            await registry.verify(ref)
            restored = await backend.read_verified(ref, max_bytes=len(payload))
            self.assertEqual(registry.decode(backend.contract, restored, ref.format_version), payload)


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
