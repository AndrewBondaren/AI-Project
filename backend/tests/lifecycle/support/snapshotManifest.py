"""Test-only terminal root extends the existing native Lifecycle fragment."""
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.encoding.canonicalCodec import merge_manifests
from tests.lifecycle.support.manifest import MOCK_NATIVE_MANIFEST
from tests.lifecycle.support.snapshotContracts import MockSnapshotApplyResult


MOCK_SNAPSHOT_MANIFEST = merge_manifests(MOCK_NATIVE_MANIFEST, CanonicalSchemaManifest(entries=(
    RegisteredTypeEntry(type_id=94001, python_type=MockSnapshotApplyResult, kind=CanonicalTypeKind.RECORD),
)))
