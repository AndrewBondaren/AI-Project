"""Time observation contracts; these records do not decide operation outcomes."""
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.time.changes.advance import PrepareAdvance
from app.dataModel.time.values.point import I64, Nano, TimeRecord
from app.dataModel.world.calendar.projection.request import CalendarProjectionInput, CalendarResolveInput
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef


class TimeLogOperation(StrEnum):
    PREPARE_ADVANCE = "prepare_advance"
    READ_CURRENT = "read_current"
    READ_HISTORICAL = "read_historical"
    PROJECT = "project"
    RESOLVE = "resolve"


class TimeLogActivity(StrEnum):
    ADVANCE_PREPARED = "advance_prepared"
    OPERATION_REFUSED = "operation_refused"
    OPERATION_CANCELLED = "operation_cancelled"
    OPERATION_FAILED = "operation_failed"


class TimeRefusalCode(StrEnum):
    ADVANCE_NONPOSITIVE = "advance_nonpositive"
    RANGE_OVERFLOW = "range_overflow"
    PUBLICATION_CONFLICT = "publication_conflict"
    INACTIVE_TIMELINE = "inactive_timeline"
    STATE_UNAVAILABLE = "state_unavailable"
    CALENDAR_SOURCE_MISMATCH = "calendar_source_mismatch"
    CALENDAR_SCOPE_MISMATCH = "calendar_scope_mismatch"
    CALENDAR_BUDGET = "calendar_budget"
    CALENDAR_INVALID = "calendar_invalid"
    CALENDAR_OVERFLOW = "calendar_overflow"


O = TimeLogOperation
C = TimeRefusalCode
REFUSALS = {
    O.PREPARE_ADVANCE: frozenset((C.ADVANCE_NONPOSITIVE, C.RANGE_OVERFLOW)),
    O.READ_CURRENT: frozenset((C.PUBLICATION_CONFLICT, C.INACTIVE_TIMELINE, C.STATE_UNAVAILABLE)),
    O.READ_HISTORICAL: frozenset((C.STATE_UNAVAILABLE,)),
    O.PROJECT: frozenset((C.CALENDAR_SOURCE_MISMATCH, C.CALENDAR_SCOPE_MISMATCH,
                          C.CALENDAR_BUDGET, C.CALENDAR_INVALID, C.CALENDAR_OVERFLOW)),
    O.RESOLVE: frozenset((C.CALENDAR_SOURCE_MISMATCH, C.CALENDAR_BUDGET,
                          C.CALENDAR_INVALID, C.CALENDAR_OVERFLOW)),
}


class TimeObservation(TimeRecord):
    operation: TimeLogOperation
    world_uid: EntityUid
    timeline_id: EntityUid | None
    operation_id: EntityUid | None
    publication_id: EntityUid | None
    snapshot: WorldSnapshotRef | None

    @field_validator("activity", mode="before", check_fields=False)
    @classmethod
    def strict_activity(cls, value: object) -> object:
        if not isinstance(value, TimeLogActivity):
            raise ValueError("activity must be TimeLogActivity")
        return value

    @model_validator(mode="after")
    def valid_operation_id(self) -> Self:
        if (self.operation is O.PREPARE_ADVANCE) != (self.operation_id is not None):
            raise ValueError("only prepare observations require an operation_id")
        if self.snapshot is not None and self.snapshot.world_uid != self.world_uid:
            raise ValueError("snapshot belongs to another world")
        return self


class TimeCandidateLog(TimeObservation):
    activity: Literal[TimeLogActivity.ADVANCE_PREPARED] = TimeLogActivity.ADVANCE_PREPARED
    operation: TimeLogOperation = TimeLogOperation.PREPARE_ADVANCE
    start_seconds: I64
    start_nanoseconds: Nano
    end_seconds: I64
    end_nanoseconds: Nano

    @model_validator(mode="after")
    def prepare_only(self) -> Self:
        if self.operation is not TimeLogOperation.PREPARE_ADVANCE:
            raise ValueError("candidate belongs to prepare only")
        return self


class TimeRefusalLog(TimeObservation):
    activity: Literal[TimeLogActivity.OPERATION_REFUSED] = TimeLogActivity.OPERATION_REFUSED
    code: TimeRefusalCode

    @model_validator(mode="after")
    def valid_code(self) -> Self:
        if self.code not in REFUSALS[self.operation]:
            raise ValueError("refusal code does not belong to operation")
        return self


class TimeCancelledLog(TimeObservation):
    activity: Literal[TimeLogActivity.OPERATION_CANCELLED] = TimeLogActivity.OPERATION_CANCELLED


class TimeFaultLog(TimeObservation):
    activity: Literal[TimeLogActivity.OPERATION_FAILED] = TimeLogActivity.OPERATION_FAILED


type TimeLogRecord = Annotated[TimeCandidateLog | TimeRefusalLog | TimeCancelledLog | TimeFaultLog,
                               Field(discriminator="activity")]


class ObservationContext(TimeRecord):
    @field_validator("operation", mode="before", check_fields=False)
    @classmethod
    def strict_operation(cls, value: object) -> object:
        if not isinstance(value, TimeLogOperation):
            raise ValueError("operation must be TimeLogOperation")
        return value


class PrepareLogContext(ObservationContext):
    operation: Literal[TimeLogOperation.PREPARE_ADVANCE] = TimeLogOperation.PREPARE_ADVANCE
    request: PrepareAdvance


class CurrentLogContext(ObservationContext):
    operation: Literal[TimeLogOperation.READ_CURRENT] = TimeLogOperation.READ_CURRENT
    expected: WorldPublicationRef


class HistoricalLogContext(ObservationContext):
    operation: Literal[TimeLogOperation.READ_HISTORICAL] = TimeLogOperation.READ_HISTORICAL
    snapshot: WorldSnapshotRef


class ProjectLogContext(ObservationContext):
    operation: Literal[TimeLogOperation.PROJECT] = TimeLogOperation.PROJECT
    request: CalendarProjectionInput


class ResolveLogContext(ObservationContext):
    operation: Literal[TimeLogOperation.RESOLVE] = TimeLogOperation.RESOLVE
    request: CalendarResolveInput


type TimeLogContext = Annotated[PrepareLogContext | CurrentLogContext | HistoricalLogContext |
                                ProjectLogContext | ResolveLogContext, Field(discriminator="operation")]
