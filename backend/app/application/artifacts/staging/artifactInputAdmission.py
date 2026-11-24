"""Pure request admission for one fixed artifact content binding."""

from pydantic import BaseModel, ValidationError

from app.application.artifacts.contracts.formatBackend import ArtifactFormatContract
from app.application.artifacts.staging.stageErrors import ArtifactInputRejected
from app.dataModel.artifacts.staging.inputErrors import ArtifactInputError, ArtifactInputIssue, ArtifactInputIssueCode
from app.dataModel.artifacts.staging.preparedArtifact import ArtifactPrepareStageInput
from app.dataModel.artifacts.staging.stageInput import ArtifactStageInput
from app.dataModel.fields.validatedFieldPath import FieldSegment, ModelIdentity, ValidatedFieldPath
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.validation.immutableValue import validate_immutable


class ArtifactInputAdmission[C: bytes | BaseModel]:
    def __init__(self, contract: ArtifactFormatContract[C]) -> None:
        self._contract = contract

    @staticmethod
    def _path(root: type[BaseModel], *fields: str) -> ValidatedFieldPath:
        # Generic envelopes have a stable source model, while their runtime
        # specialization is fixed by the owning format composition.
        owner = ModelIdentity(module=root.__module__, qualname=root.__qualname__)
        return ValidatedFieldPath(root=owner,
            segments=tuple(FieldSegment(owner=owner, name=name) for name in fields))

    @staticmethod
    def _reject(errors: ValidatorAggregationHelper[ArtifactInputIssue]) -> None:
        errors.raise_if_any(lambda issues: ArtifactInputRejected(ArtifactInputError(issues=issues)))

    def _content(self, content: object, root: type[BaseModel],
                 errors: ValidatorAggregationHelper[ArtifactInputIssue]) -> None:
        if type(content) is not self._contract.content_model:
            errors.add(ArtifactInputIssue(code=ArtifactInputIssueCode.CONTENT_TYPE_MISMATCH,
                path=self._path(root, "content"), message="content has another concrete type"))
            return
        try:
            if isinstance(content, BaseModel):
                type(content).model_validate(content, strict=True)
            validate_immutable(content)
        except (ValueError, ValidationError) as error:
            errors.add(ArtifactInputIssue(code=ArtifactInputIssueCode.CONTENT_NOT_IMMUTABLE,
                path=self._path(root, "content"), message="content is not a complete immutable value"))

    def prepare(self, request: ArtifactPrepareStageInput[C]) -> ArtifactPrepareStageInput[C]:
        errors = ValidatorAggregationHelper((ArtifactInputIssue,))
        self._content(request.content, ArtifactPrepareStageInput, errors)
        self._reject(errors)
        return request

    def stage(self, request: ArtifactStageInput[C]) -> ArtifactStageInput[C]:
        errors = ValidatorAggregationHelper((ArtifactInputIssue,))
        self._content(request.prepared.content, ArtifactStageInput, errors)
        descriptor = request.prepared.descriptor
        if (descriptor.kind is not self._contract.kind or descriptor.format_key != self._contract.key
                or descriptor.format_version not in self._contract.supported_versions):
            errors.add(ArtifactInputIssue(code=ArtifactInputIssueCode.FORMAT_BINDING_MISMATCH,
                path=self._path(ArtifactStageInput, "prepared"), message="descriptor has another format binding"))
        self._reject(errors)
        return request
