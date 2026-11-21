"""Current-only terminal representation and configuration admission."""
import unittest
from dataclasses import replace

from app.application.encoding.boundedCanonicalDecode import decode_bounded, validate_bounded, validate_decode_limits
from app.application.publication.contracts.resultBinding import PublicationResultBinding
from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.encoding.coreManifest import SNAPSHOT_CORE_SCHEMA
from app.dataModel.artifacts.lifecycle.operation.record import OperationRecord
from app.dataModel.encoding.decodeLimits import DecodeLimits
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, RegisteredTypeEntry, CanonicalTypeKind
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult
from app.dataModel.worldSnapshot.results.applyIssues import SnapshotApplyRelationIssue, SnapshotApplyCode
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.db.repositories.sqlite.snapshotCore.operations.terminalCodec import StoredTerminalCodec
from app.encoding.canonicalCodec import CanonicalEncodingError, encode, content_digest, merge_manifests


class CurrentResult(SnapshotApplyResult):
    diagnostics: tuple[SnapshotApplyRelationIssue, ...]


class CurrentPublicationTests(unittest.TestCase):
    def setUp(self):
        self.limits = DecodeLimits(max_bytes=100000, max_nodes=10000, max_depth=100, max_items=1000)
        self.schema = merge_manifests(SNAPSHOT_CORE_SCHEMA, CanonicalSchemaManifest(entries=(
            RegisteredTypeEntry(type_id=94001, python_type=CurrentResult, kind=CanonicalTypeKind.RECORD),
        )))
        self.binding = PublicationResultBinding(result_model=CurrentResult, snapshot_format_version=1,
            manifest=self.schema, record_model=OperationRecord[CurrentResult], limits=self.limits)
        self.codec = StoredTerminalCodec(binding=self.binding)
        self.result = CurrentResult(category=SnapshotApplyOutcomeKind.REJECTED, operation_id="op",
            request_fingerprint="a" * 64, committed=None, diagnostics=(SnapshotApplyRelationIssue(
                code=SnapshotApplyCode.GAMEPLAY_NOT_STARTED, section_key=None, player_uid=None, artifact=None),))

    def test_roundtrip_preserves_concrete_result_and_diagnostic(self):
        row = self.codec.encode(self.result)
        restored = self.codec.decode(row)
        self.assertIs(type(restored), CurrentResult)
        self.assertEqual(restored, self.result)
        self.assertIs(type(restored.diagnostics[0]), SnapshotApplyRelationIssue)

    def test_old_root_and_unknown_format_are_not_absence(self):
        row = self.codec.encode(self.result)
        old = SnapshotApplyResult(**{name: getattr(self.result, name) for name in CurrentResult.model_fields})
        data = encode(old, self.schema)
        with self.assertRaises(PublicationInfrastructureError):
            self.codec.decode(replace(row, outcome_data=data, outcome_checksum=content_digest(data).hex()))
        with self.assertRaises(PublicationInfrastructureError):
            self.codec.decode(replace(row, format_version=2))
        with self.assertRaises(TypeError):
            self.codec.encode(old)

    def test_record_model_must_match(self):
        with self.assertRaises(ValueError):
            replace(self.binding, record_model=OperationRecord[SnapshotApplyResult])

    def test_missing_nested_manifest_type_is_rejected_at_construction(self):
        schema = CanonicalSchemaManifest(entries=tuple(entry for entry in self.schema.entries
            if entry.python_type is not SnapshotApplyCode))
        with self.assertRaises(ValueError):
            replace(self.binding, manifest=schema)

    def test_row_identity_and_category_must_match_body(self):
        row = self.codec.encode(self.result)
        for altered in (replace(row, operation_id="other"), replace(row, category="conflict")):
            with self.assertRaises(PublicationInfrastructureError):
                self.codec.decode(altered)

    def test_config_errors_precede_malformed_payload(self):
        for entry in (decode_bounded, validate_bounded):
            for value, error in ((True, TypeError), (0, ValueError), (-1, ValueError)):
                with self.subTest(entry=entry.__name__, value=value):
                    with self.assertRaises(error) as caught:
                        entry(b"bad", CurrentResult, self.schema, limits=replace(self.limits, max_bytes=value))
                    self.assertNotIsInstance(caught.exception, CanonicalEncodingError)
            with self.assertRaises(CanonicalEncodingError):
                entry(b"bad", CurrentResult, self.schema, limits=self.limits)

    def test_duplicate_field_owner_is_configuration_error(self):
        from app.dataModel.encoding.decodeLimits import RecordLimits
        record = RecordLimits(CurrentResult, ())
        with self.assertRaises(ValueError):
            validate_decode_limits(replace(self.limits, field_sizes=(record, record)))
