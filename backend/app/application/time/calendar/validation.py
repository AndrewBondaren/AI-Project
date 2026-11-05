from app.dataModel.registryKey import RegistryKey
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.world.calendar.definitions.definition import CalendarDefinition, CalendarEntry
from app.dataModel.world.calendar.definitions.registry import WorldCalendarRegistry
from app.dataModel.world.calendar.projection.errors import CalendarBudgetExceeded, CalendarInvalid
from app.dataModel.world.calendar.projection.request import CalendarBudget, ValidateCalendarInput
from app.dataModel.world.calendar.projection.result import CalendarValidated
from app.dataModel.world.calendar.rules.edits import InsertSpanRule, RemoveSpanRule
from app.dataModel.world.settings.timeSettings import WorldTimeSettings
from .ordinal import CalendarIndex
from .rules import ExhaustedBudget, InvalidCalendar, Work


def _validate_definition(definition: CalendarDefinition, hours: int, work: Work) -> CalendarIndex:
    spans = {s.system_span for s in definition.spans.entries}
    seasons = {s.system_season for s in definition.seasons.entries}
    base = definition.base_year
    if len({s.span for s in base}) != len(base):
        raise InvalidCalendar(("base_year",), "duplicate occurrence")
    values = list(base)
    for rule in definition.rules:
        if isinstance(rule, RemoveSpanRule):
            if rule.span not in spans:
                raise InvalidCalendar(("rules",), "unknown removed span")
        else:
            values.append(rule.value)
            if isinstance(rule, InsertSpanRule) and rule.after is not None and rule.after not in spans:
                raise InvalidCalendar(("rules",), "unknown insertion anchor")
    if any(s.span not in spans or (s.season is not None and s.season not in seasons) for s in values):
        raise InvalidCalendar(("spans",), "unknown span or season")
    periods = definition.periods.entries
    starts = {p.start for p in periods}
    if (0, 0) not in starts or max(starts) >= (hours, 0) or len(starts) != len(periods):
        raise InvalidCalendar(("periods",), "invalid period boundaries")
    if definition.week_anchor_index >= max(1, len(definition.weekdays.entries)):
        raise InvalidCalendar(("week_anchor_index",), "invalid weekday anchor")
    return CalendarIndex(definition, work)


def validate_entry(entry: CalendarEntry, hours: int, work: Work) -> CalendarIndex:
    try:
        index = _validate_definition(entry.definition, hours, work)
    except InvalidCalendar as error:
        raise InvalidCalendar(("definition", *error.path), str(error)) from error
    if entry.anchor.origin.time.hour >= hours:
        raise InvalidCalendar(("anchor", "origin", "time"), "hour outside day")
    try:
        index.ordinal(entry.anchor.origin.date)
    except InvalidCalendar as error:
        raise InvalidCalendar(("anchor", "origin", *error.path), str(error)) from error
    return index


def validated_indexes(settings: WorldTimeSettings, budget: CalendarBudget) -> dict[RegistryKey[WorldCalendarRegistry], CalendarIndex]:
    work = Work.from_budget(budget)
    indices = {}
    for i, entry in enumerate(settings.calendars.entries):
        try:
            indices[entry.definition.system_calendar] = validate_entry(entry, settings.hours_per_day, work)
        except InvalidCalendar as error:
            raise InvalidCalendar(("calendars", "entries", i, *error.path), str(error)) from error
    if settings.selected not in indices:
        raise InvalidCalendar(("selected",), "unknown selected calendar")
    seen = set()
    for i, epoch in enumerate(settings.epochs.entries):
        key = epoch.calendar, epoch.start_seconds, epoch.start_nanoseconds
        if key in seen or epoch.calendar not in indices:
            raise InvalidCalendar(("epochs", "entries", i), "invalid epoch calendar or duplicate start")
        indices[epoch.calendar].astronomical(epoch.start_year_label)
        seen.add(key)
    return indices


def invalid(error: InvalidCalendar) -> CalendarInvalid:
    return CalendarInvalid(issues=(FieldPathError(path=error.path, message=str(error)),))


class CalendarValidator:
    @staticmethod
    def validate(request: ValidateCalendarInput) -> CalendarValidated | CalendarInvalid | CalendarBudgetExceeded:
        try:
            validated_indexes(request.settings, request.budget)
        except ExhaustedBudget:
            return CalendarBudgetExceeded(budget=request.budget)
        except InvalidCalendar as error:
            return invalid(error)
        return CalendarValidated(settings=request.settings)
