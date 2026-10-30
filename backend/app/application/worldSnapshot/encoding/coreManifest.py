"""Snapshot schema v1, including patch/artifact shared dependency declarations."""

from app.application.patch.encoding.coreManifest import PATCH_CORE_SCHEMA
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.worldSnapshot.metadata.envelope import WorldSnapshotMetadata, PlayerSnapshotMetadata
from app.dataModel.worldSnapshot.events import SnapshotLogActivity, SnapshotLogRecord


SNAPSHOT_CORE_SCHEMA = CanonicalSchemaManifest(entries=PATCH_CORE_SCHEMA.entries + tuple(
    RegisteredTypeEntry(type_id=identity, python_type=owner, kind=kind)
    for identity, owner, kind in (
        (20014, SnapshotLogActivity, CanonicalTypeKind.ENUM),
        (20133, WorldSnapshotMetadata, CanonicalTypeKind.RECORD),
        (20134, PlayerSnapshotMetadata, CanonicalTypeKind.RECORD),
        (20135, SnapshotLogRecord, CanonicalTypeKind.RECORD),
    )
))
