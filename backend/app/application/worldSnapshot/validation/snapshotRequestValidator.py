"""Adapt owning PatchSet admission and prepared order to one public fault."""
from app.application.patch.encoding.patchSetCodec import PatchSetCodec
from app.application.patch.errors import PatchSetAdmissionError
from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.errors import SnapshotPublicError
from app.application.worldSnapshot.validation.publicInputValidation import SnapshotPublicInputValidation
from app.dataModel.patch.request.patchSet import PatchSet
from app.dataModel.patch.sections.section import DomainSection
from app.dataModel.patch.validation.admissionReasons import PatchSetRequestModelMismatch, PatchSetStructuralFailure
from app.dataModel.patch.validation.patchSetInvariants import PatchSetInvariants
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireLocation import WireLocation
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue
from app.dataModel.worldSnapshot.errors.publicFault import (
    SnapshotInputIssue, SNAPSHOT_INPUT_ISSUE_TYPES, SnapshotPublicFault,
    SnapshotPublicFailureKind, SnapshotPublicOperation,
)


class SnapshotRequestValidator[S: DomainSection]:
    def __init__(self, codec: PatchSetCodec[S]) -> None:
        self._codec = codec

    def validate(self, request: PatchSet[S]) -> PatchSet[S]:
        issues = ValidatorAggregationHelper[SnapshotInputIssue](SNAPSHOT_INPUT_ISSUE_TYPES)
        try:
            checked = self._codec.validate_request(request)
        except PatchSetAdmissionError as error:
            for reason in error.reasons:
                if type(reason) is PatchSetRequestModelMismatch:
                    issues.add(WireShapeIssue(code=JsonValidationCode.VALIDATION_ERROR, location=WireLocation(),
                        message="request must have the configured concrete model", pydantic_type=None))
                elif type(reason) is PatchSetStructuralFailure:
                    for issue in SnapshotPublicInputValidation.map_structural(reason, model=self._codec.request_model):
                        issues.add(issue)
                elif type(reason) in SNAPSHOT_INPUT_ISSUE_TYPES:
                    issues.add(reason)  # pyright: ignore[reportArgumentType]
                else:
                    raise PublicationInfrastructureError("unknown PatchSet admission reason") from error
            raise self._refusal(issues.snapshot()) from error
        for violation in PatchSetInvariants.check_prepared_order(checked):
            issues.add(violation)
        issues.raise_if_any(self._refusal)
        return checked

    @staticmethod
    def _refusal(issues: tuple[SnapshotInputIssue, ...]) -> SnapshotPublicError:
        relation = any(type(issue) not in (JsonFieldError, WireShapeIssue) for issue in issues)
        return SnapshotPublicError(SnapshotPublicFault(operation=SnapshotPublicOperation.APPLY,
            kind=SnapshotPublicFailureKind.ADMISSION_REFUSED if relation else SnapshotPublicFailureKind.INVALID_INPUT,
            operation_id=None, request_fingerprint=None, input_issues=issues))
