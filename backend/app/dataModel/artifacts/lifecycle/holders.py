"""Typed holder identities are distinct from the operation kind they wrap."""

from enum import StrEnum
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef
from app.dataModel.worldSnapshot.identity.refs import SnapshotRef


class ArtifactHolderKind(StrEnum):
    OPERATION = "operation"
    ARTIFACT = "artifact"
    SNAPSHOT = "snapshot"


class OperationHolder(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    kind: Literal[ArtifactHolderKind.OPERATION] = ArtifactHolderKind.OPERATION
    lease: OperationLeaseRef


class ArtifactRetentionHolder(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    kind: Literal[ArtifactHolderKind.ARTIFACT] = ArtifactHolderKind.ARTIFACT
    artifact: ArtifactRef


class SnapshotHolder(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    kind: Literal[ArtifactHolderKind.SNAPSHOT] = ArtifactHolderKind.SNAPSHOT
    snapshot: SnapshotRef


type ArtifactHolderRef = Annotated[
    OperationHolder | ArtifactRetentionHolder | SnapshotHolder, Field(discriminator="kind"),
]


class VerifiedArtifactRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    ref: ArtifactRef
    holder: ArtifactHolderRef
