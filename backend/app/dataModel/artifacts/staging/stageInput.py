"""In-memory request for fenced artifact staging."""

from pydantic import BaseModel, ConfigDict
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef
from app.dataModel.artifacts.staging.preparedArtifact import PreparedArtifact


class ArtifactStageInput[C: bytes | BaseModel](BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="never")
    lease: OperationLeaseRef
    prepared: PreparedArtifact[C]
