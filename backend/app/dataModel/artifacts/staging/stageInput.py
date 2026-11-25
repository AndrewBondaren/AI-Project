"""In-memory request for fenced artifact staging."""

from pydantic import BaseModel, ConfigDict
from typing import Annotated
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef
from app.dataModel.artifacts.staging.preparedArtifact import ArtifactInstanceSchema, PreparedArtifact, PreparedArtifactBase


class ArtifactStageInputBase(BaseModel):
    """Named diagnostic root, independent of the runtime payload specialization."""
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="never")
    lease: OperationLeaseRef
    prepared: PreparedArtifactBase


class ArtifactStageInput[C: bytes | BaseModel](ArtifactStageInputBase):
    prepared: Annotated[PreparedArtifact[C], ArtifactInstanceSchema]
