"""Expected failure of an exact fenced artifact lease requirement."""

from enum import StrEnum
from pydantic import BaseModel, ConfigDict, model_validator
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef


class ArtifactLeaseRequirement(StrEnum):
    WRITABLE = "WRITABLE"
    CLOSED = "CLOSED"


class ArtifactLeaseFailureCode(StrEnum):
    OPERATION_MISSING = "OPERATION_MISSING"
    BINDING_MISMATCH = "BINDING_MISMATCH"
    FENCE_MISMATCH = "FENCE_MISMATCH"
    LEASE_ABSENT = "LEASE_ABSENT"
    PHASE_NOT_WRITABLE = "PHASE_NOT_WRITABLE"
    ADMISSION_CLOSED = "ADMISSION_CLOSED"
    ADMISSION_OPEN = "ADMISSION_OPEN"


class ArtifactLeaseFailure(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")
    lease: OperationLeaseRef
    requirement: ArtifactLeaseRequirement
    code: ArtifactLeaseFailureCode

    @model_validator(mode="after")
    def _compatible(self):
        if self.code in (ArtifactLeaseFailureCode.PHASE_NOT_WRITABLE,
                         ArtifactLeaseFailureCode.ADMISSION_CLOSED) and self.requirement is not ArtifactLeaseRequirement.WRITABLE:
            raise ValueError("failure code requires writable admission")
        if self.code is ArtifactLeaseFailureCode.ADMISSION_OPEN and self.requirement is not ArtifactLeaseRequirement.CLOSED:
            raise ValueError("failure code requires closed admission")
        return self
