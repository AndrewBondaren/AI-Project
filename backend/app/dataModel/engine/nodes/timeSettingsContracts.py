"""Named Time settings leaf transport."""
from app.dataModel.world.calendar.scalars import CalendarRecord
from app.dataModel.engine.dag.errors.nodeError import NodeError
from app.dataModel.world.calendar.projection.errors import CalendarBudgetExceeded
from app.dataModel.world.settings.timeOperations.changes import HoursChange, CalendarCreate, CalendarUpdate, CalendarSelect, CalendarRemove, EpochCreate, EpochUpdate, EpochRemove
from app.dataModel.world.settings.timeOperations.results import PreparedTimeSettingsChange, SettingsInvalid, SettingsAnchorRequired, SettingsInUse

class TimeSettingsNodeError(NodeError):
    pass

class PrepareHoursChangeInput(CalendarRecord):
    request: HoursChange

class PrepareHoursChangeOutput(CalendarRecord):
    value: PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded | SettingsAnchorRequired

class PrepareCalendarCreateInput(CalendarRecord):
    request: CalendarCreate

class PrepareCalendarCreateOutput(CalendarRecord):
    value: PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded

class PrepareCalendarUpdateInput(CalendarRecord):
    request: CalendarUpdate

class PrepareCalendarUpdateOutput(CalendarRecord):
    value: PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded | SettingsAnchorRequired

class PrepareCalendarSelectInput(CalendarRecord):
    request: CalendarSelect

class PrepareCalendarSelectOutput(CalendarRecord):
    value: PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded

class PrepareCalendarRemoveInput(CalendarRecord):
    request: CalendarRemove

class PrepareCalendarRemoveOutput(CalendarRecord):
    value: PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded | SettingsInUse

class PrepareEpochCreateInput(CalendarRecord):
    request: EpochCreate

class PrepareEpochCreateOutput(CalendarRecord):
    value: PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded

class PrepareEpochUpdateInput(CalendarRecord):
    request: EpochUpdate

class PrepareEpochUpdateOutput(CalendarRecord):
    value: PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded

class PrepareEpochRemoveInput(CalendarRecord):
    request: EpochRemove

class PrepareEpochRemoveOutput(CalendarRecord):
    value: PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded
