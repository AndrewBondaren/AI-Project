"""Minimal owning composition for the historical preparation binding."""
from app.application.artifacts.encoding.coreManifest import ARTIFACT_CORE_SCHEMA
from app.application.worldData.sourceVersioning.encoding.sourceProofRequestSchemaV1 import SOURCE_PROOF_REQUEST_ENCODING_V1
from app.dataModel.artifacts.lifecycle.holders import (
    ArtifactHolderKind, OperationHolder, ArtifactRetentionHolder, SnapshotHolder, PinHolder, VerifiedArtifactRef,
)
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.publication.preparationSourceAuthority import (
    PreparationSourceOriginKind, PinnedManifestSourceOrigin, PreparationSourceBinding,
)
from app.dataModel.worldPack.encoding.pinBindings import PACK_PIN_SCHEMA
from app.dataModel.worldSnapshot.identity.refs import SnapshotChainKind, WorldSnapshotRef, PlayerSnapshotRef
from app.encoding.canonicalCodec import CanonicalEncodingError, merge_manifests


PREPARATION_SOURCE_SCHEMA = CanonicalSchemaManifest(entries=(
    RegisteredTypeEntry(type_id=20308, python_type=PreparationSourceOriginKind, kind=CanonicalTypeKind.ENUM),
    RegisteredTypeEntry(type_id=20309, python_type=PinnedManifestSourceOrigin, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=20310, python_type=PreparationSourceBinding, kind=CanonicalTypeKind.RECORD),
))


def _artifact_dependencies() -> CanonicalSchemaManifest:
    entries: list[RegisteredTypeEntry] = []
    for owner in (SnapshotChainKind, ArtifactKind, OperationKind, ArtifactHolderKind,
                  WorldSnapshotRef, PlayerSnapshotRef, ArtifactRef, OperationLeaseRef,
                  OperationHolder, ArtifactRetentionHolder, SnapshotHolder, VerifiedArtifactRef, PinHolder):
        matches = tuple(entry for entry in ARTIFACT_CORE_SCHEMA.entries if entry.python_type is owner)
        if len(matches) != 1:
            raise CanonicalEncodingError("missing or ambiguous Artifact dependency")
        entries.append(matches[0])
    return CanonicalSchemaManifest(entries=tuple(entries))


PREPARATION_SOURCE_ENCODING = merge_manifests(
    _artifact_dependencies(), SOURCE_PROOF_REQUEST_ENCODING_V1, PACK_PIN_SCHEMA, PREPARATION_SOURCE_SCHEMA,
)
