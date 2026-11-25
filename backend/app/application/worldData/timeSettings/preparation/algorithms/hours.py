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

from app.dataModel.world.settings.timeOperations.changes import HoursChange


from ..shared.context import CandidatePreparation


def hours_change(request: HoursChange, context: CandidatePreparation) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded | SettingsAnchorRequired:
    base = request.base
    settings = context.settings
    replacements = {item.calendar: item.origin for item in request.anchors}
    keys = {e.definition.system_calendar for e in settings.calendars.entries}
    if len(replacements) != len(request.anchors) or replacements.keys() - keys:
        return issue(CheckedPath.root(HoursChange).field(FieldRef(lambda: HoursChange, lambda value: value.anchors)), "duplicate or unknown calendar")
    entries = []
    for entry in settings.calendars.entries:
        key = entry.definition.system_calendar
        origin = replacements.get(key)
        if origin is None:
            current = context.project(key)
            if not isinstance(current, (CalendarProjection, CalendarOrigin)):
                return current
            if current.time.hour >= request.hours_per_day:
                return SettingsAnchorRequired(calendar=key, current=current.time)
            origin = CalendarOrigin(date=current.date, time=current.time)
        point = base.clock.point
        anchor = CalendarAnchor(coordinate_seconds=point.seconds, coordinate_nanoseconds=point.nanoseconds, origin=origin)
        entries.append(CalendarEntry(definition=entry.definition, anchor=anchor))
    candidate = settings.model_copy(update={"hours_per_day": request.hours_per_day,
                                           "calendars": WorldCalendarRegistry(entries=tuple(entries))})
    return context.prepare(candidate)

