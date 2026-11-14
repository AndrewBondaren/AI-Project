"""Infrastructure/recovery errors are not domain apply outcomes."""
from app.dataModel.publication.operationBindingMismatch import OperationBindingMismatch


class OperationBindingMismatchError(ValueError):
    def __init__(self, mismatch: OperationBindingMismatch) -> None:
        self.mismatch = OperationBindingMismatch.model_validate(mismatch, strict=True)
        super().__init__(self.mismatch)


class PublicationInfrastructureError(RuntimeError):
    pass


class UnknownCommitOutcome(PublicationInfrastructureError):
    pass


class OperationBusyError(RuntimeError):
    pass
