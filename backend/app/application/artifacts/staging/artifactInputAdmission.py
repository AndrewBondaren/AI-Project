"""Pure request admission for one fixed artifact content binding."""

from pydantic import BaseModel, ValidationError

from app.application.artifacts.contracts.formatBackend import ArtifactFormatContract
from app.application.artifacts.staging.stageErrors import ArtifactInputRejected
from app.dataModel.artifacts.staging.inputErrors import ArtifactInputError, ArtifactInputIssue, ArtifactInputIssueCode
from app.dataModel.artifacts.staging.preparedArtifact import ArtifactPrepareStageInput, ArtifactPrepareStageInputBase, PreparedArtifactBase
from app.dataModel.artifacts.staging.stageInput import ArtifactStageInput, ArtifactStageInputBase
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.fields.validatedFieldPath import ValidatedFieldPath
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.artifacts.staging.contentValidation import validate_content_instance


class ArtifactInputAdmission[C: bytes | BaseModel]:
    def __init__(self, contract: ArtifactFormatContract[C]) -> None:
        self._contract = contract

    @staticmethod
    def _reject(errors: ValidatorAggregationHelper[ArtifactInputIssue]) -> None:
        errors.raise_if_any(lambda issues: ArtifactInputRejected(ArtifactInputError(issues=issues)))

    def _content(self, content: object, path: ValidatedFieldPath,
                 errors: ValidatorAggregationHelper[ArtifactInputIssue]) -> None:
        if type(content) is not self._contract.content_model:
            errors.add(ArtifactInputIssue(code=ArtifactInputIssueCode.CONTENT_TYPE_MISMATCH,
                path=path, message="content has another concrete type"))
            return
        try:
            validate_content_instance(content)
        except (ValueError, ValidationError) as error:
            errors.add(ArtifactInputIssue(code=ArtifactInputIssueCode.CONTENT_NOT_IMMUTABLE,
                path=path, message="content is not a complete immutable value"))

    def prepare(self, request: ArtifactPrepareStageInput[C]) -> ArtifactPrepareStageInput[C]:
        errors = ValidatorAggregationHelper((ArtifactInputIssue,))
        content: FieldRef[ArtifactPrepareStageInputBase, bytes | BaseModel] = FieldRef(
            lambda: ArtifactPrepareStageInputBase, lambda value: value.content)
        self._content(content.select(request), CheckedPath.root(ArtifactPrepareStageInputBase).field(content).freeze(), errors)
        self._reject(errors)
        return request

    def stage(self, request: ArtifactStageInput[C]) -> ArtifactStageInput[C]:
        errors = ValidatorAggregationHelper((ArtifactInputIssue,))
        prepared_field: FieldRef[ArtifactStageInputBase, PreparedArtifactBase] = FieldRef(
            lambda: ArtifactStageInputBase, lambda value: value.prepared)
        content_field: FieldRef[PreparedArtifactBase, bytes | BaseModel] = FieldRef(
            lambda: PreparedArtifactBase, lambda value: value.content)
        prepared_path = CheckedPath.root(ArtifactStageInputBase).field(prepared_field)
        prepared = prepared_field.select(request)
        self._content(content_field.select(prepared), prepared_path.field(content_field).freeze(), errors)
        descriptor = prepared.descriptor
        if (descriptor.kind is not self._contract.kind or descriptor.format_key != self._contract.key
                or descriptor.format_version not in self._contract.supported_versions):
            errors.add(ArtifactInputIssue(code=ArtifactInputIssueCode.FORMAT_BINDING_MISMATCH,
                path=prepared_path.freeze(), message="descriptor has another format binding"))
        self._reject(errors)
        return request
