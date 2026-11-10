"""Result of a durably finished World Pack preparation."""
from pydantic import BaseModel, ConfigDict

from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.identity.uid import EntityUid
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex


class PreparedPackCandidate(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    operation_id: EntityUid
    manifest: ArtifactRef
    preparation_fingerprint: RevisionHex
