"""Private SQLite test composition; not the Lifecycle or production wire allocation."""
from app.application.publication.contracts.resultBinding import PublicationResultBinding
from app.dataModel.artifacts.lifecycle.operation.record import OperationRecord
from app.dataModel.encoding.decodeLimits import DecodeLimits
from app.dataModel.fields.validatedFieldPath import IndexSegment, KeySegment, VariantSegment
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult
from app.dataModel.worldSnapshot.results.applyIssues import SnapshotApplyRelationIssue
from app.encoding.canonicalCodec import merge_manifests
from tests.snapshotCore.support.diagnostics import TEST_ISSUE_SCHEMA
from tests.snapshotCore.support.fakeSection import FakeTargetIssue


class SnapshotTestResult(SnapshotApplyResult[FakeTargetIssue]):
    diagnostics: tuple[SnapshotApplyRelationIssue | FakeTargetIssue, ...]


# Same isolated current-root test slot as test_publication_current_binding;
# these test manifests are never merged or used for production/Lifecycle data.
TEST_PUBLICATION_BINDING = PublicationResultBinding(
    result_model=SnapshotTestResult,
    snapshot_format_version=1,
    manifest=merge_manifests(TEST_ISSUE_SCHEMA, CanonicalSchemaManifest(entries=(
        RegisteredTypeEntry(type_id=94001, python_type=SnapshotTestResult, kind=CanonicalTypeKind.RECORD),
        RegisteredTypeEntry(type_id=90015, python_type=IndexSegment, kind=CanonicalTypeKind.RECORD),
        RegisteredTypeEntry(type_id=90016, python_type=KeySegment, kind=CanonicalTypeKind.RECORD),
        RegisteredTypeEntry(type_id=90017, python_type=VariantSegment, kind=CanonicalTypeKind.RECORD),
    ))),
    record_model=OperationRecord[SnapshotTestResult],
    limits=DecodeLimits(max_bytes=100000, max_nodes=10000, max_depth=100, max_items=1000),
)
