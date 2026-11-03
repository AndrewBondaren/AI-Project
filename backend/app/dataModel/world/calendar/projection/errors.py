from pydantic import Field

from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.time.values.point import TimeScope
from ..enums.rules import CalendarConversionKind
from .request import CalendarBudget
from app.dataModel.world.calendar.scalars import CalendarRecord
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef


class CalendarSourceMismatch(CalendarRecord):
    expected: WorldPublicationRef | WorldSnapshotRef
    actual: WorldPublicationRef | WorldSnapshotRef


class CalendarScopeMismatch(CalendarRecord):
    expected: TimeScope
    actual: TimeScope


class CalendarBudgetExceeded(CalendarRecord):
    budget: CalendarBudget


class CalendarInvalid(CalendarRecord):
    issues: tuple[FieldPathError, ...] = Field(min_length=1)


class CalendarTimeOverflow(CalendarRecord):
    operation: CalendarConversionKind
