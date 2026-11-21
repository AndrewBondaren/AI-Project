from typing import Self

from pydantic import Field, ValidationError, model_validator
from pydantic_core import InitErrorDetails

from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.identity.uid import EntityUid
from app.dataModel.patch.changes.patchData import PatchData
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
        if (header.ref.section_key != CLOCK_SECTION or header.ref.ordinal != 0
                or header.format_version != TIME_ADVANCE_PATCH_FORMAT
                or header.depends_on or header.artifacts
                or header.ref.operation_id != self.proposal.operation_id):
            raise ValueError("invalid native Time advance patch header")
        return self


class TimeAdvanceSection(DomainSection[TimeAdvancePatch]):
    patches: tuple[TimeAdvancePatch, ...] = Field(min_length=1, max_length=1)

    @model_validator(mode="after")
    def native_header(self) -> Self:
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
            if field.select(self.header) != expected:
                errors.add(TimeSectionFieldIssue(path=header.field(field).freeze(), code=code, message=code.value))
        errors.raise_if_any(lambda issues: ValidationError.from_exception_data(type(self).__name__, [
            InitErrorDetails(type="value_error", loc=issue.path.projection(),
                             input=getattr(self.header, issue.path.projection()[-1]),
                             ctx={"error": ValueError(issue.message)}) for issue in issues
        ]))
        return self
