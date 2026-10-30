"""Publication claim alternatives returned by the common operation store."""

from typing import Annotated, Literal, Self
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationClaimKind, OperationPhase
from app.dataModel.artifacts.lifecycle.operation.record import OperationRecord


class PublicationOwner(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    kind: Literal[OperationClaimKind.OWNER] = OperationClaimKind.OWNER
    lease: OperationLeaseRef


class PublicationTerminal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    kind: Literal[OperationClaimKind.TERMINAL] = OperationClaimKind.TERMINAL
    record: OperationRecord

    @model_validator(mode="after")
    def terminal_record(self) -> Self:
        if self.record.phase is not OperationPhase.TERMINAL:
            raise ValueError("terminal claim requires a terminal record")
        return self


class PublicationBusy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    kind: Literal[OperationClaimKind.BUSY] = OperationClaimKind.BUSY
    record: OperationRecord

    @model_validator(mode="after")
    def nonterminal_record(self) -> Self:
        if self.record.phase is OperationPhase.TERMINAL:
            raise ValueError("busy claim cannot contain a terminal record")
        return self


type OperationClaim = Annotated[
    PublicationOwner | PublicationTerminal | PublicationBusy, Field(discriminator="kind"),
]
