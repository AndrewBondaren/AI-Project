from typing import Self

from pydantic import Field, ValidationError, ValidationInfo, ModelWrapValidatorHandler, model_validator
from pydantic_core import InitErrorDetails

from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.identity.uid import EntityUid
from app.dataModel.patch.changes.patchData import PatchData
from app.dataModel.patch.changes.header import PatchHeader, PatchRef
from app.dataModel.patch.sections.section import DomainSection, SectionHeader
from app.dataModel.time.changes.advance import TimeAdvanceProposal
from app.dataModel.time.results.section import TimeSectionFieldIssue, TimeSectionIssueCode
from app.dataModel.time.storage.state import CLOCK_SECTION
from app.dataModel.time.values.point import TimeRecord
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef

from .admission import raw_field, valid_field, json_collections

TIME_ADVANCE_PATCH_FORMAT = 1
TIME_ADVANCE_SECTION_FORMAT = 1


class PrepareTimeAdvanceSection(TimeRecord):
    proposal: TimeAdvanceProposal
    operation_id: EntityUid
    expected_world: WorldPublicationRef


class TimeAdvancePatch(PatchData):
    proposal: TimeAdvanceProposal

    @model_validator(mode="wrap")
    @classmethod
    def native_header(cls, value: object, handler: ModelWrapValidatorHandler[Self], info: ValidationInfo) -> Self:
        if info.mode == "json":
            value = json_collections(value)
        structural = []
        result = None
        try:
            result = handler(value)
        except ValidationError as error:
            structural = error.errors(include_url=False)
        errors = ValidatorAggregationHelper((TimeSectionFieldIssue,))
        header_field = FieldRef(lambda: TimeAdvancePatch, lambda patch: patch.header)
        ref_field = FieldRef(lambda: PatchHeader, lambda header: header.ref)
        header = raw_field(value, header_field)
        ref_value = raw_field(header, ref_field)
        path = CheckedPath.root(TimeAdvancePatch).field(header_field)
        ref = path.field(ref_field)
        proposal = raw_field(value, FieldRef(lambda: TimeAdvancePatch, lambda patch: patch.proposal))
        operation = valid_field(proposal, FieldRef(lambda: TimeAdvanceProposal, lambda proposal: proposal.operation_id))
        checks = (
            (ref, ref_value, FieldRef(lambda: PatchRef, lambda ref: ref.section_key),
             CLOCK_SECTION, TimeSectionIssueCode.INVALID_KEY),
            (ref, ref_value, FieldRef(lambda: PatchRef, lambda ref: ref.ordinal),
             0, TimeSectionIssueCode.INVALID_ORDINAL),
            (path, header, FieldRef(lambda: PatchHeader, lambda header: header.format_version),
             TIME_ADVANCE_PATCH_FORMAT, TimeSectionIssueCode.UNSUPPORTED_VERSION),
            (path, header, FieldRef(lambda: PatchHeader, lambda header: header.depends_on),
             (), TimeSectionIssueCode.DEPENDENCIES_FORBIDDEN),
            (path, header, FieldRef(lambda: PatchHeader, lambda header: header.artifacts),
             (), TimeSectionIssueCode.ARTIFACTS_FORBIDDEN),
            (ref, ref_value, FieldRef(lambda: PatchRef, lambda ref: ref.operation_id),
             operation, TimeSectionIssueCode.OPERATION_MISMATCH),
        )
        inputs = {}
        for parent, owner, field, expected, code in checks:
            actual = valid_field(owner, field)
            if actual is not None and expected is not None and actual != expected:
                frozen = parent.field(field).freeze()
                inputs[frozen.projection()] = actual
                errors.add(TimeSectionFieldIssue(path=frozen, code=code, message=code.value))
        details = [*structural, *[
            InitErrorDetails(type="value_error", loc=issue.path.projection(),
                             input=inputs[issue.path.projection()], ctx={"error": ValueError(issue.message)})
            for issue in errors.snapshot()
        ]]
        if details:
            raise ValidationError.from_exception_data(cls.__name__, details)
        assert result is not None
        return result


class TimeAdvanceSection(DomainSection[TimeAdvancePatch]):
    patches: tuple[TimeAdvancePatch, ...] = Field(min_length=1, max_length=1)

    @model_validator(mode="wrap")
    @classmethod
    def native_header(cls, value: object, handler: ModelWrapValidatorHandler[Self], info: ValidationInfo) -> Self:
        if info.mode == "json":
            value = json_collections(value)
        structural = []
        result = None
        try:
            result = handler(value)
        except ValidationError as error:
            structural = error.errors(include_url=False)
        raw_header = raw_field(value, FieldRef(lambda: TimeAdvanceSection, lambda section: section.header))
        errors = ValidatorAggregationHelper((TimeSectionFieldIssue,))
        header = CheckedPath.root(TimeAdvanceSection).field(
            FieldRef(lambda: TimeAdvanceSection, lambda value: value.header))
        checks = (
            (FieldRef(lambda: SectionHeader, lambda value: value.key), CLOCK_SECTION,
             TimeSectionIssueCode.INVALID_KEY),
            (FieldRef(lambda: SectionHeader, lambda value: value.format_version), TIME_ADVANCE_SECTION_FORMAT,
             TimeSectionIssueCode.UNSUPPORTED_VERSION),
            (FieldRef(lambda: SectionHeader, lambda value: value.depends_on), (),
             TimeSectionIssueCode.DEPENDENCIES_FORBIDDEN),
        )
        inputs = {}
        for field, expected, code in checks:
            actual = valid_field(raw_header, field)
            if actual is not None and actual != expected:
                inputs[header.field(field).freeze().projection()] = actual
                errors.add(TimeSectionFieldIssue(path=header.field(field).freeze(), code=code, message=code.value))
        details = [*structural, *[
            InitErrorDetails(type="value_error", loc=issue.path.projection(),
                             input=inputs[issue.path.projection()], ctx={"error": ValueError(issue.message)})
            for issue in errors.snapshot()
        ]]
        details.sort(key=lambda detail: 0 if detail["loc"][:1] == ("header",) else 1)
        if details:
            raise ValidationError.from_exception_data(cls.__name__, details)
        assert result is not None
        return result
