"""All diagnostics observed during a failed read, in domain-defined order."""
from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.spatial.read.request import SpatialReadRequest
from app.dataModel.spatial.readFailureReason import SpatialReadFailureReason
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class SpatialReadError(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    reason: SpatialReadFailureReason
    issue: FieldPathError


class SpatialReadFailure(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    request: SpatialReadRequest
    errors: tuple[SpatialReadError, ...] = Field(min_length=1)
