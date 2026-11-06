"""Explicit observation of Time outcomes using the existing logging facade."""
import logging

from app.core.logLevel import LogLevel, to_logging_level
from app.dataModel.time.diagnostics.events import (
    TimeLogRecord, TimeLogContext, TimeObservation, TimeLogActivity, TimeLogOperation,
    TimeRefusalCode, TimeCandidateLog, TimeRefusalLog, TimeCancelledLog, TimeFaultLog,
    PrepareLogContext, CurrentLogContext, HistoricalLogContext, ProjectLogContext, ResolveLogContext,
)
from app.dataModel.time.changes.advance import PrepareAdvance, TimeAdvanceProposal
from app.dataModel.time.results.errors import (
    TimeAdvanceMustBePositive, TimeRangeOverflow, TimePublicationConflict,
    TimeInactiveTimeline, TimeStateUnavailable,
)
from app.dataModel.time.reads.capture import TimeCapture
from app.dataModel.world.calendar.projection.errors import (
    CalendarSourceMismatch, CalendarScopeMismatch, CalendarBudgetExceeded, CalendarInvalid, CalendarTimeOverflow,
)
from app.dataModel.world.calendar.projection.request import CalendarProjectionInput, CalendarResolveInput
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef

type CalendarRefusal = CalendarSourceMismatch | CalendarBudgetExceeded | CalendarInvalid | CalendarTimeOverflow
type Refusal = (TimeAdvanceMustBePositive | TimeRangeOverflow | TimePublicationConflict |
                TimeInactiveTimeline | TimeStateUnavailable | CalendarRefusal | CalendarScopeMismatch)

_CODES = {
    TimeAdvanceMustBePositive: TimeRefusalCode.ADVANCE_NONPOSITIVE,
    TimeRangeOverflow: TimeRefusalCode.RANGE_OVERFLOW,
    TimePublicationConflict: TimeRefusalCode.PUBLICATION_CONFLICT,
    TimeInactiveTimeline: TimeRefusalCode.INACTIVE_TIMELINE,
    TimeStateUnavailable: TimeRefusalCode.STATE_UNAVAILABLE,
    CalendarSourceMismatch: TimeRefusalCode.CALENDAR_SOURCE_MISMATCH,
    CalendarScopeMismatch: TimeRefusalCode.CALENDAR_SCOPE_MISMATCH,
    CalendarBudgetExceeded: TimeRefusalCode.CALENDAR_BUDGET,
    CalendarInvalid: TimeRefusalCode.CALENDAR_INVALID,
    CalendarTimeOverflow: TimeRefusalCode.CALENDAR_OVERFLOW,
}
_LEVELS = {
    TimeLogActivity.ADVANCE_PREPARED: LogLevel.DEBUG,
    TimeLogActivity.OPERATION_REFUSED: LogLevel.WARNING,
    TimeLogActivity.OPERATION_CANCELLED: LogLevel.DEBUG,
    TimeLogActivity.OPERATION_FAILED: LogLevel.ERROR,
}


def _observation(context: TimeLogContext) -> TimeObservation:
    if type(context) not in (PrepareLogContext, CurrentLogContext, HistoricalLogContext,
                             ProjectLogContext, ResolveLogContext):
        raise TypeError("expected a concrete Time logging context")
    context = type(context).model_validate(context, strict=True)
    operation_id = None
    match context:
        case PrepareLogContext(request=request):
            source = request.base.publication
            timeline = request.base.point.timeline_id
            operation_id = request.operation_id
        case CurrentLogContext(expected=source):
            timeline = source.active_timeline_id
        case HistoricalLogContext(snapshot=source):
            timeline = source.timeline_id
        case ProjectLogContext(request=request):
            capture = request.capture
            source = capture.publication if isinstance(capture, TimeCapture) else capture.snapshot
            timeline = capture.point.timeline_id
        case ResolveLogContext(request=request):
            source = request.resolved.source
            timeline = request.scope.timeline_id
    return TimeObservation(operation=context.operation, world_uid=source.world_uid,
        timeline_id=timeline, operation_id=operation_id,
        publication_id=source.publication_id if isinstance(source, WorldPublicationRef) else None,
        snapshot=source.snapshot_head if isinstance(source, WorldPublicationRef) else source)


class TimeOperationLog:
    def __init__(self) -> None:
        self._logger = logging.getLogger("app.time.operations")

    def emit(self, record: TimeLogRecord) -> None:
        if type(record) not in (TimeCandidateLog, TimeRefusalLog, TimeCancelledLog, TimeFaultLog):
            raise TypeError("expected a concrete Time log record")
        record = type(record).model_validate(record, strict=True)
        extra = record.model_dump(mode="json", serialize_as_any=False)
        level = to_logging_level(_LEVELS[record.activity])
        try:
            self._logger.log(level, record.activity.value, extra=extra)
        except Exception:
            pass

    def _refused(self, context: TimeLogContext, refusal: Refusal) -> None:
        code = _CODES.get(type(refusal))
        if code is None:
            raise TypeError("unexpected Time refusal")
        type(refusal).model_validate(refusal, strict=True)
        self.emit(TimeRefusalLog(**_observation(context).model_dump(), code=code))

    def emit_advance_prepared(self, proposal: TimeAdvanceProposal) -> None:
        proposal = TimeAdvanceProposal.model_validate(proposal, strict=True)
        source = proposal.base.publication
        interval = proposal.interval
        self.emit(TimeCandidateLog(world_uid=source.world_uid, timeline_id=proposal.base.point.timeline_id,
            operation_id=proposal.operation_id, publication_id=source.publication_id, snapshot=source.snapshot_head,
            start_seconds=interval.start.seconds, start_nanoseconds=interval.start.nanoseconds,
            end_seconds=interval.end.seconds, end_nanoseconds=interval.end.nanoseconds))

    def emit_advance_refused(self, request: PrepareAdvance,
                             refusal: TimeAdvanceMustBePositive | TimeRangeOverflow) -> None:
        self._refused(PrepareLogContext(request=request), refusal)

    def emit_current_refused(self, expected: WorldPublicationRef,
                             refusal: TimePublicationConflict | TimeInactiveTimeline | TimeStateUnavailable) -> None:
        self._refused(CurrentLogContext(expected=expected), refusal)

    def emit_historical_refused(self, snapshot: WorldSnapshotRef, refusal: TimeStateUnavailable) -> None:
        self._refused(HistoricalLogContext(snapshot=snapshot), refusal)

    def emit_project_refused(self, request: CalendarProjectionInput,
                             refusal: CalendarRefusal | CalendarScopeMismatch) -> None:
        self._refused(ProjectLogContext(request=request), refusal)

    def emit_resolve_refused(self, request: CalendarResolveInput, refusal: CalendarRefusal) -> None:
        self._refused(ResolveLogContext(request=request), refusal)

    def emit_cancelled(self, context: TimeLogContext) -> None:
        self.emit(TimeCancelledLog(**_observation(context).model_dump()))

    def emit_fault(self, context: TimeLogContext) -> None:
        self.emit(TimeFaultLog(**_observation(context).model_dump()))
