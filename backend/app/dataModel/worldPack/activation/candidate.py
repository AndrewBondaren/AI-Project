"""Result of a durably finished World Pack preparation."""
from pydantic import BaseModel, ConfigDict, field_validator

from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.worldPack.meta.manifestStorageFormat import MANIFEST_FORMAT_KEY, MANIFEST_STORAGE_VERSION
from app.dataModel.identity.uid import EntityUid
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex


class PreparedPackCandidate(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    operation_id: EntityUid
    manifest: ArtifactRef
    preparation_fingerprint: RevisionHex

    @field_validator("manifest")
    @classmethod
    def require_manifest_descriptor(cls, ref: ArtifactRef) -> ArtifactRef:
        if (ref.kind is not ArtifactKind.BLOB or ref.format_key != MANIFEST_FORMAT_KEY
                or ref.format_version != MANIFEST_STORAGE_VERSION or ref.nbytes <= 0):
            raise ValueError("candidate requires a World Pack V2 manifest descriptor")
        return ref
