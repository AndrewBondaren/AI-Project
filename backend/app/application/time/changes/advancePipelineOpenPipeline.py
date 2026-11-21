from typing import Protocol

from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.patch.changes.header import PatchHeader, PatchRef
from app.dataModel.patch.sections.section import SectionHeader
from app.dataModel.time.changes.section import PrepareTimeAdvanceSection, TimeAdvancePatch, TimeAdvanceSection, TIME_ADVANCE_PATCH_FORMAT, TIME_ADVANCE_SECTION_FORMAT
from app.dataModel.time.results.section import TimeSectionContextMismatch, TimeSectionFieldIssue, TimeSectionIssueCode
from app.dataModel.time.reads.capture import TimeCapture
from app.dataModel.time.storage.state import CLOCK_SECTION
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper

from app.application.time.pure.arithmetic import TimeArithmetic
from app.dataModel.time.changes.advance import PrepareAdvance, TimeAdvanceProposal
from app.dataModel.time.operations.arithmetic import AddDurationInput
from app.dataModel.time.results.errors import TimeAdvanceMustBePositive, TimeRangeOverflow
from app.dataModel.time.values.interval import TimeInterval


class ITimeAdvancePipelineOpenPipeline(Protocol):
    def prepare_section(self, request: PrepareTimeAdvanceSection) -> TimeAdvanceSection | TimeSectionContextMismatch: ...

    def prepare_advance(self, request: PrepareAdvance) -> TimeAdvanceProposal | TimeAdvanceMustBePositive | TimeRangeOverflow: ...


class TimeAdvancePipelineOpenPipeline:
    def prepare_section(self, request: PrepareTimeAdvanceSection) -> TimeAdvanceSection | TimeSectionContextMismatch:
        errors = ValidatorAggregationHelper((TimeSectionFieldIssue,))
        proposal = request.proposal
        path = CheckedPath.root(PrepareTimeAdvanceSection).field(
            FieldRef(lambda: PrepareTimeAdvanceSection, lambda value: value.proposal))
        operation = FieldRef(lambda: TimeAdvanceProposal, lambda value: value.operation_id)
        publication = FieldRef(lambda: TimeCapture, lambda value: value.publication)
        if operation.select(proposal) != request.operation_id:
            errors.add(TimeSectionFieldIssue(path=path.field(operation).freeze(),
                code=TimeSectionIssueCode.OPERATION_MISMATCH, message="proposal operation differs from supplied context"))
        if publication.select(proposal.base) != request.expected_world:
            errors.add(TimeSectionFieldIssue(path=path.field(
                FieldRef(lambda: TimeAdvanceProposal, lambda value: value.base)).field(publication).freeze(),
                code=TimeSectionIssueCode.PUBLICATION_MISMATCH, message="proposal publication differs from supplied context"))
        issues = errors.snapshot()
        if issues:
            return TimeSectionContextMismatch(issues=issues)
        patch = TimeAdvancePatch(proposal=proposal, header=PatchHeader(
            ref=PatchRef(operation_id=request.operation_id, section_key=CLOCK_SECTION, ordinal=0),
            format_version=TIME_ADVANCE_PATCH_FORMAT, depends_on=(), artifacts=()))
        return TimeAdvanceSection(header=SectionHeader(key=CLOCK_SECTION,
            format_version=TIME_ADVANCE_SECTION_FORMAT, depends_on=()), patches=(patch,))

    def prepare_advance(self, request: PrepareAdvance) -> TimeAdvanceProposal | TimeAdvanceMustBePositive | TimeRangeOverflow:
        duration = request.duration
        if duration.seconds == duration.nanoseconds == 0:
            return TimeAdvanceMustBePositive(duration=duration)
        start = request.base.point
        result = TimeArithmetic.add(AddDurationInput(point=start, duration=duration))
        if isinstance(result, TimeRangeOverflow):
            return result
        return TimeAdvanceProposal(operation_id=request.operation_id, base=request.base,
                                   interval=TimeInterval(start=start, end=result.point))
