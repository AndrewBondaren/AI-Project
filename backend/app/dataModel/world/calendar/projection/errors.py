from enum import StrEnum

from pydantic import BaseModel, Field
from app.dataModel.fields.checkedPath import CheckedPath

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


class CalendarIssueCode(StrEnum):
    INVALID_CALENDAR = "invalid_calendar"
    INVALID_SETTINGS_CHANGE = "invalid_settings_change"


class CalendarFieldIssue(FieldPathError[CalendarIssueCode]):
    @classmethod
    def at(cls, root: type[BaseModel], loc: tuple[str | int, ...], code: CalendarIssueCode, message: str):
        path = CheckedPath.from_pydantic_loc(root, loc)
        if path is None:
            raise ValueError(f"invalid diagnostic path for {root.__name__}: {loc}")
        return cls(path=path, code=code, message=message)


class CalendarInvalid(CalendarRecord):
    issues: tuple[CalendarFieldIssue, ...] = Field(min_length=1)


class CalendarTimeOverflow(CalendarRecord):
    operation: CalendarConversionKind
