"""A persisted operation cancellation is distinct from cancellation of a call."""
from app.dataModel.artifacts.lifecycle.operation.record import OperationCancelled
from typing import Annotated
from pydantic import Field, TypeAdapter
from app.application.publication.errors import PublicationInfrastructureError
from app.dataModel.worldSnapshot.diagnostics.receiptContract import ReceiptContractIssue
from app.dataModel.worldSnapshot.errors.publicFault import SnapshotPublicFault


class SnapshotPublicError(Exception):
    def __init__(self, fault: SnapshotPublicFault) -> None:
        self.fault = SnapshotPublicFault.model_validate(fault, strict=True)
        super().__init__(self.fault.kind.value)


class SnapshotReceiptContractError(PublicationInfrastructureError):
    def __init__(self, diagnostics: tuple[ReceiptContractIssue, ...]) -> None:
        self.diagnostics = TypeAdapter(Annotated[tuple[ReceiptContractIssue, ...], Field(min_length=1)]).validate_python(
            diagnostics, strict=True)
        super().__init__(self.diagnostics)


class SnapshotOperationCancelledError(Exception):
    def __init__(self, outcome: OperationCancelled) -> None:
        self.outcome = OperationCancelled.model_validate(outcome, strict=True)
        super().__init__(self.outcome)
