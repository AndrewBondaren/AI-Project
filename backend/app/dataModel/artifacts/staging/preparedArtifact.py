"""In-memory artifact preparation envelopes."""

from pydantic import BaseModel, ConfigDict
from app.dataModel.artifacts.references import ArtifactRef


class ArtifactPrepareStageInput[C: bytes | BaseModel](BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="never")
    content: C


class PreparedArtifact[C: bytes | BaseModel](BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="never")
    content: C
    descriptor: ArtifactRef
