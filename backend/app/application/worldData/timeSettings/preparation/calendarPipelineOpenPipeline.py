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
from app.dataModel.world.settings.timeOperations.changes import CalendarCreate, CalendarUpdate, CalendarSelect, CalendarRemove
from app.dataModel.world.settings.timeOperations.results import SettingsInUse


class WorldCalendarSettingsPipelineOpenPipeline:
    def __init__(self, validator: CalendarValidator, projector: CalendarProjector):
        self._validator = validator
        self._projector = projector

    def prepare_calendar_create(self, request: CalendarCreate) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded:
        settings = request.base.capture.settings
        entries = settings.calendars.entries
        if any(e.definition.system_calendar == request.entry.definition.system_calendar for e in entries):
            return issue(request, "entry", "calendar already exists")
        registry = WorldCalendarRegistry(entries=(*entries, request.entry))
        return prepare(request.base, settings.model_copy(update={"calendars": registry}), self._validator)

    def prepare_calendar_update(self, request: CalendarUpdate) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded | SettingsAnchorRequired:
        base = request.base
        settings = base.capture.settings
        key = request.entry.definition.system_calendar
        current = projected(base, key, self._projector)
        if not isinstance(current, CalendarProjection):
            return current
        point = base.clock.point
        entry = request.entry
        explicit = (entry.anchor.coordinate_seconds, entry.anchor.coordinate_nanoseconds) == point.coordinate
        previous = settings.calendars.entry_for(key)
        if not explicit and previous is not None and entry.anchor != previous.anchor:
            return issue(request, "entry.anchor", "replacement anchor must be at the effective point")
        if not explicit:
            anchor = CalendarAnchor(coordinate_seconds=point.seconds, coordinate_nanoseconds=point.nanoseconds,
                                    origin=CalendarOrigin(date=current.date, time=current.time))
            entry = CalendarEntry(definition=entry.definition, anchor=anchor)
        entries = tuple(entry if e.definition.system_calendar == key else e for e in settings.calendars.entries)
        candidate = settings.model_copy(update={"calendars": WorldCalendarRegistry(entries=entries)})
        result = prepare(base, candidate, self._validator)
        if not explicit and isinstance(result, SettingsInvalid) and all(
            i.path.projection()[3:5] == ("anchor", "origin") for i in result.issues
        ):
            return SettingsAnchorRequired(calendar=key, current=current.time)
        return result

    def prepare_calendar_select(self, request: CalendarSelect) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded:
        candidate = request.base.capture.settings.model_copy(update={"selected": request.calendar})
        return prepare(request.base, candidate, self._validator)

    def prepare_calendar_remove(self, request: CalendarRemove) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded | SettingsInUse:
        settings = request.base.capture.settings
        keys = {e.definition.system_calendar for e in settings.calendars.entries}
        if request.calendar not in keys or request.replacement not in keys - {request.calendar}:
            return issue(request, "replacement", "existing distinct replacement required")
        if any(epoch.calendar == request.calendar for epoch in settings.epochs.entries):
            return SettingsInUse(calendar=request.calendar)
        entries = tuple(e for e in settings.calendars.entries if e.definition.system_calendar != request.calendar)
        selected = request.replacement if settings.selected == request.calendar else settings.selected
        candidate = settings.model_copy(update={"selected": selected, "calendars": WorldCalendarRegistry(entries=entries)})
        return prepare(request.base, candidate, self._validator)
