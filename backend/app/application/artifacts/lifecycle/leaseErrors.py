"""Expected artifact lease refusal carrier."""

from app.dataModel.artifacts.lifecycle.leaseFailure import ArtifactLeaseFailure


class ArtifactLeaseRefused(Exception):
    def __init__(self, failure: ArtifactLeaseFailure) -> None:
        self.failure = ArtifactLeaseFailure.model_validate(failure, strict=True)
        super().__init__(failure.code.value)
