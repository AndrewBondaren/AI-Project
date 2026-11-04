"""Domain facts for one window and the immutable sources behind them."""
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.spatial.read.failure import SpatialReadFailure
from app.dataModel.spatial.read.request import SpatialReadMode, SpatialReadRequest
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


type SpatialSourceRef = PlanRef | ArtifactRef


class SpatialSlice[T](BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    request: SpatialReadRequest
    payload: T
    source_refs: tuple[SpatialSourceRef, ...] = Field(min_length=1)
    issues: tuple[FieldPathError, ...]

    @field_validator("source_refs", mode="before")
    @classmethod
    def typed_refs(cls, value: object) -> object:
        if not isinstance(value, tuple) or not all(isinstance(ref, (PlanRef, ArtifactRef)) for ref in value):
            raise ValueError("expected a tuple of typed source refs")
        return value

    @model_validator(mode="after")
    def provenance(self) -> Self:
        revision = self.request.revision
        world = revision.key.world_uid if isinstance(revision, PlanRef) else revision.world_uid
        if len(set(self.source_refs)) != len(self.source_refs):
            raise ValueError("duplicate source ref")
        if any(isinstance(ref, PlanRef) and ref.key.world_uid != world for ref in self.source_refs):
            raise ValueError("source belongs to another world")
        if isinstance(revision, PlanRef):
            if revision not in self.source_refs:
                raise ValueError("missing requested bootstrap revision")
        else:
            if revision.pack_hash is None:
                raise ValueError("successful Pack read requires a pinned Pack")
            if not any(isinstance(ref, ArtifactRef) and ref.kind is ArtifactKind.BLOB for ref in self.source_refs):
                raise ValueError("missing Pack BLOB source")
        if self.issues and self.request.mode is SpatialReadMode.REQUIRED:
            raise ValueError("required slice has issues")
        return self


type SpatialReadResult[T] = SpatialSlice[T] | SpatialReadFailure
