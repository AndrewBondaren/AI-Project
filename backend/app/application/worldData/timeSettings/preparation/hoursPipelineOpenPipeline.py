from app.application.time.calendar.validation import CalendarValidator
from app.dataModel.world.calendar.projection.errors import CalendarBudgetExceeded
from app.dataModel.world.settings.timeOperations.results import PreparedTimeSettingsChange, SettingsInvalid
from .shared.candidate import issue, prepare
from app.application.time.calendar.projection import CalendarProjector
from app.dataModel.world.calendar.dates.anchor import CalendarAnchor, CalendarOrigin
from app.dataModel.world.calendar.definitions.definition import CalendarEntry
from app.dataModel.world.calendar.definitions.registry import WorldCalendarRegistry
from app.dataModel.world.calendar.projection.result import CalendarProjection
from app.dataModel.world.settings.timeOperations.results import SettingsAnchorRequired
from .shared.candidate import projected
from app.dataModel.world.settings.timeOperations.changes import HoursChange


class WorldHoursSettingsPipelineOpenPipeline:
    def __init__(self, validator: CalendarValidator, projector: CalendarProjector):
        self._validator = validator
        self._projector = projector

    def prepare_hours_change(self, request: HoursChange) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded | SettingsAnchorRequired:
        base = request.base
        settings = base.capture.settings
        replacements = {item.calendar: item.origin for item in request.anchors}
        keys = {e.definition.system_calendar for e in settings.calendars.entries}
        if len(replacements) != len(request.anchors) or replacements.keys() - keys:
            return issue(request, "anchors", "duplicate or unknown calendar")
        entries = []
        for entry in settings.calendars.entries:
            key = entry.definition.system_calendar
            origin = replacements.get(key)
            if origin is None:
                current = projected(base, key, self._projector)
                if not isinstance(current, CalendarProjection):
                    return current
                if current.time.hour >= request.hours_per_day:
                    return SettingsAnchorRequired(calendar=key, current=current.time)
                origin = CalendarOrigin(date=current.date, time=current.time)
            point = base.clock.point
            anchor = CalendarAnchor(coordinate_seconds=point.seconds, coordinate_nanoseconds=point.nanoseconds, origin=origin)
            entries.append(CalendarEntry(definition=entry.definition, anchor=anchor))
        candidate = settings.model_copy(update={"hours_per_day": request.hours_per_day,
                                               "calendars": WorldCalendarRegistry(entries=tuple(entries))})
        return prepare(base, candidate, self._validator)
