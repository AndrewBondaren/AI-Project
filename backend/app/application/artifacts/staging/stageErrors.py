"""Expected input refusal, without logging or storage effects."""

from app.dataModel.artifacts.staging.inputErrors import ArtifactInputError


class ArtifactInputRejected(Exception):
    def __init__(self, error: ArtifactInputError) -> None:
        self.error = ArtifactInputError.model_validate(error, strict=True)
        super().__init__("artifact input rejected")
