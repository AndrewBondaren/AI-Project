"""Canonical immutable Snapshot metadata envelopes; no world payload or state restore."""

from dataclasses import dataclass
from typing import ClassVar

from app.application.encoding.canonicalCodec import CanonicalEncodingError, decode as canonical_decode, encode as canonical_encode, merge_manifests
from app.application.worldSnapshot.encoding.coreManifest import SNAPSHOT_CORE_SCHEMA
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest
from app.dataModel.patch.values import FormatVersion
from app.dataModel.worldSnapshot.metadata.envelope import SnapshotEnvelope, WorldSnapshotMetadata, PlayerSnapshotMetadata


@dataclass(frozen=True, slots=True)
class SnapshotEnvelopeCodec:
    manifest: CanonicalSchemaManifest = SNAPSHOT_CORE_SCHEMA
    SUPPORTED_VERSIONS: ClassVar[frozenset[FormatVersion]] = frozenset({1})

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest", merge_manifests(SNAPSHOT_CORE_SCHEMA, self.manifest))

    def encode(self, envelope: SnapshotEnvelope) -> bytes:
        if type(envelope) not in (WorldSnapshotMetadata, PlayerSnapshotMetadata):
            raise CanonicalEncodingError("expected a world/player metadata envelope")
        type(envelope).model_validate(envelope, strict=True)
        if envelope.envelope_format_version not in self.SUPPORTED_VERSIONS:
            raise CanonicalEncodingError("unsupported Snapshot envelope format")
        return canonical_encode(envelope, self.manifest)

    def decode(self, payload: bytes) -> SnapshotEnvelope:
        value = canonical_decode(payload, object, self.manifest)
        if not isinstance(value, (WorldSnapshotMetadata, PlayerSnapshotMetadata)):
            raise CanonicalEncodingError("canonical record is not a Snapshot metadata envelope")
        if value.envelope_format_version not in self.SUPPORTED_VERSIONS:
            raise CanonicalEncodingError("unsupported Snapshot envelope format")
        return value
