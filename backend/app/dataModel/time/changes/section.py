from typing import Self

from pydantic import Field, ValidationError, field_validator, model_validator
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

TIME_ADVANCE_PATCH_FORMAT = 1
TIME_ADVANCE_SECTION_FORMAT = 1


class PrepareTimeAdvanceSection(TimeRecord):
    proposal: TimeAdvanceProposal
    operation_id: EntityUid
    expected_world: WorldPublicationRef


class TimeAdvancePatch(PatchData):
    proposal: TimeAdvanceProposal

    @model_validator(mode="after")
    def native_header(self) -> Self:
        header = self.header
        errors = ValidatorAggregationHelper((TimeSectionFieldIssue,))
        path = CheckedPath.root(TimeAdvancePatch).field(
            FieldRef(lambda: TimeAdvancePatch, lambda value: value.header))
        ref = path.field(FieldRef(lambda: PatchHeader, lambda value: value.ref))
        checks = (
            (ref.field(FieldRef(lambda: PatchRef, lambda value: value.section_key)),
             header.ref.section_key, CLOCK_SECTION, TimeSectionIssueCode.INVALID_KEY),
            (ref.field(FieldRef(lambda: PatchRef, lambda value: value.ordinal)),
             header.ref.ordinal, 0, TimeSectionIssueCode.INVALID_ORDINAL),
            (path.field(FieldRef(lambda: PatchHeader, lambda value: value.format_version)),
             header.format_version, TIME_ADVANCE_PATCH_FORMAT, TimeSectionIssueCode.UNSUPPORTED_VERSION),
            (path.field(FieldRef(lambda: PatchHeader, lambda value: value.depends_on)),
             header.depends_on, (), TimeSectionIssueCode.DEPENDENCIES_FORBIDDEN),
            (path.field(FieldRef(lambda: PatchHeader, lambda value: value.artifacts)),
             header.artifacts, (), TimeSectionIssueCode.ARTIFACTS_FORBIDDEN),
            (ref.field(FieldRef(lambda: PatchRef, lambda value: value.operation_id)),
             header.ref.operation_id, self.proposal.operation_id, TimeSectionIssueCode.OPERATION_MISMATCH),
        )
        inputs = {}
        for checked_path, actual, expected, code in checks:
            if actual != expected:
                frozen = checked_path.freeze()
                inputs[frozen.projection()] = actual
                errors.add(TimeSectionFieldIssue(path=frozen, code=code, message=code.value))
        errors.raise_if_any(lambda issues: ValidationError.from_exception_data(type(self).__name__, [
            InitErrorDetails(type="value_error", loc=issue.path.projection(),
                             input=inputs[issue.path.projection()], ctx={"error": ValueError(issue.message)})
            for issue in issues
        ]))
        return self


class TimeAdvanceSection(DomainSection[TimeAdvancePatch]):
    patches: tuple[TimeAdvancePatch, ...] = Field(min_length=1, max_length=1)

    @field_validator("header")
    @classmethod
    def native_header(cls, value: SectionHeader) -> SectionHeader:
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
        for field, expected, code in checks:
            if field.select(value) != expected:
                errors.add(TimeSectionFieldIssue(path=header.field(field).freeze(), code=code, message=code.value))
        errors.raise_if_any(lambda issues: ValidationError.from_exception_data(cls.__name__, [
            InitErrorDetails(type="value_error", loc=issue.path.projection()[1:],
                             input=getattr(value, issue.path.projection()[-1]),
                             ctx={"error": ValueError(issue.message)}) for issue in issues
        ]))
        return value
