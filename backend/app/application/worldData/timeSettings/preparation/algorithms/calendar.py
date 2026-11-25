from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.world.calendar.projection.errors import CalendarBudgetExceeded
from app.dataModel.world.settings.timeOperations.results import PreparedTimeSettingsChange, SettingsInvalid
from ..shared.candidate import issue
from app.dataModel.world.calendar.dates.anchor import CalendarAnchor, CalendarOrigin
from app.dataModel.world.calendar.definitions.definition import CalendarEntry
from app.dataModel.world.calendar.definitions.registry import WorldCalendarRegistry
from app.dataModel.world.calendar.projection.result import CalendarProjection
from app.dataModel.world.settings.timeOperations.results import SettingsAnchorRequired

from app.dataModel.world.settings.timeOperations.changes import CalendarCreate, CalendarUpdate, CalendarSelect, CalendarRemove
from app.dataModel.world.settings.timeOperations.results import SettingsInUse


from ..shared.context import CandidatePreparation


def calendar_create(request: CalendarCreate, context: CandidatePreparation) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded:
    settings = context.settings
    entries = settings.calendars.entries
    if any(e.definition.system_calendar == request.entry.definition.system_calendar for e in entries):
        return issue(CheckedPath.root(CalendarCreate).field(FieldRef(lambda: CalendarCreate, lambda value: value.entry)), "calendar already exists")
    registry = WorldCalendarRegistry(entries=(*entries, request.entry))
    return context.prepare(settings.model_copy(update={"calendars": registry}))


def calendar_update(request: CalendarUpdate, context: CandidatePreparation) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded | SettingsAnchorRequired:
    base = request.base
    settings = context.settings
    key = request.entry.definition.system_calendar
    current = context.project(key)
    if not isinstance(current, (CalendarProjection, CalendarOrigin)):
        return current
    point = base.clock.point
    entry = request.entry
    explicit = (entry.anchor.coordinate_seconds, entry.anchor.coordinate_nanoseconds) == point.coordinate
    previous = settings.calendars.entry_for(key)
    if not explicit and previous is not None and entry.anchor != previous.anchor:
        return issue(CheckedPath.root(CalendarUpdate).field(FieldRef(lambda: CalendarUpdate, lambda value: value.entry)).field(FieldRef(lambda: CalendarEntry, lambda value: value.anchor)), "replacement anchor must be at the effective point")
    if not explicit:
        anchor = CalendarAnchor(coordinate_seconds=point.seconds, coordinate_nanoseconds=point.nanoseconds,
                                origin=CalendarOrigin(date=current.date, time=current.time))
        entry = CalendarEntry(definition=entry.definition, anchor=anchor)
    entries = tuple(entry if e.definition.system_calendar == key else e for e in settings.calendars.entries)
    candidate = settings.model_copy(update={"calendars": WorldCalendarRegistry(entries=entries)})
    result = context.prepare(candidate)
    if not explicit and isinstance(result, SettingsInvalid) and all(
        i.path.projection()[3:5] == ("anchor", "origin") for i in result.issues
    ):
        return SettingsAnchorRequired(calendar=key, current=current.time)
    return result


def calendar_select(request: CalendarSelect, context: CandidatePreparation) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded:
    candidate = context.settings.model_copy(update={"selected": request.calendar})
    return context.prepare(candidate)


def calendar_remove(request: CalendarRemove, context: CandidatePreparation) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded | SettingsInUse:
    settings = context.settings
    keys = {e.definition.system_calendar for e in settings.calendars.entries}
    if request.calendar not in keys or request.replacement not in keys - {request.calendar}:
        return issue(CheckedPath.root(CalendarRemove).field(FieldRef(lambda: CalendarRemove, lambda value: value.replacement)), "existing distinct replacement required")
    if any(epoch.calendar == request.calendar for epoch in settings.epochs.entries):
        return SettingsInUse(calendar=request.calendar)
    entries = tuple(e for e in settings.calendars.entries if e.definition.system_calendar != request.calendar)
    selected = request.replacement if settings.selected == request.calendar else settings.selected
    candidate = settings.model_copy(update={"selected": selected, "calendars": WorldCalendarRegistry(entries=entries)})
    return context.prepare(candidate)

