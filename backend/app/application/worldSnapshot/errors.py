"""A persisted operation cancellation is distinct from cancellation of a call."""
from app.dataModel.artifacts.lifecycle.operation.record import OperationCancelled


class SnapshotOperationCancelledError(Exception):
    def __init__(self, outcome: OperationCancelled) -> None:
        self.outcome = OperationCancelled.model_validate(outcome, strict=True)
        super().__init__(self.outcome)
