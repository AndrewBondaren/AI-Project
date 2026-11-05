from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.registryKey import RegistryKey
from pydantic import BaseModel
from app.dataModel.world.calendar.projection.errors import CalendarFieldIssue, CalendarIssueCode
from app.dataModel.world.calendar.definitions.definition import CalendarDefinition, CalendarEntry
from app.dataModel.world.calendar.definitions.registry import WorldCalendarRegistry
from app.dataModel.world.calendar.projection.errors import CalendarBudgetExceeded, CalendarInvalid
from app.dataModel.world.calendar.projection.request import CalendarBudget, ValidateCalendarInput
from app.dataModel.world.calendar.projection.result import CalendarValidated
from app.dataModel.world.calendar.rules.edits import InsertSpanRule, RemoveSpanRule
from app.dataModel.world.settings.timeSettings import WorldTimeSettings
from .ordinal import CalendarIndex
from .rules import ExhaustedBudget, InvalidCalendar, Work


def _validate_definition(definition: CalendarDefinition, work: Work) -> CalendarIndex:
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
    return CalendarIndex(definition, work)


def validated_indexes(settings: WorldTimeSettings, budget: CalendarBudget, issues: ValidatorAggregationHelper[CalendarFieldIssue] | None = None) -> dict[RegistryKey[WorldCalendarRegistry], CalendarIndex]:
    work = Work.from_budget(budget)
    def record(path: tuple[str | int, ...], message: str) -> None:
        if issues is None:
            raise InvalidCalendar(path, message)
        issues.add(CalendarFieldIssue.at(WorldTimeSettings, path, CalendarIssueCode.INVALID_CALENDAR, message))

    indices = {}
    for i, entry in enumerate(settings.calendars.entries):
        prefix = ("calendars", "entries", i)
        definition = entry.definition
        periods = definition.periods.entries
        starts = {p.start for p in periods}
        if (0, 0) not in starts or max(starts) >= (settings.hours_per_day, 0) or len(starts) != len(periods):
            record((*prefix, "definition", "periods"), "invalid period boundaries")
        if definition.week_anchor_index >= max(1, len(definition.weekdays.entries)):
            record((*prefix, "definition", "week_anchor_index"), "invalid weekday anchor")
        if entry.anchor.origin.time.hour >= settings.hours_per_day:
            record((*prefix, "anchor", "origin", "time", "hour"), "hour outside day")
        try:
            index = _validate_definition(definition, work)
        except InvalidCalendar as error:
            record((*prefix, "definition", *error.path), str(error))
            continue
        indices[definition.system_calendar] = index
        try:
            index.ordinal(entry.anchor.origin.date)
        except InvalidCalendar as error:
            date_path = ("date", "year") if error.path == ("year",) else error.path
            record((*prefix, "anchor", "origin", *date_path), str(error))
    if settings.calendars.entry_for(settings.selected) is None:
        record(("selected",), "unknown selected calendar")
    seen = set()
    for i, epoch in enumerate(settings.epochs.entries):
        key = epoch.calendar, epoch.start_seconds, epoch.start_nanoseconds
        if key in seen or settings.calendars.entry_for(epoch.calendar) is None:
            record(("epochs", "entries", i), "invalid epoch calendar or duplicate start")
        if epoch.calendar in indices:
            try:
                indices[epoch.calendar].astronomical(epoch.start_year_label)
            except InvalidCalendar as error:
                record(("epochs", "entries", i, "start_year_label"), str(error))
        seen.add(key)
    return indices


def invalid(error: InvalidCalendar, root: type[BaseModel] = WorldTimeSettings) -> CalendarInvalid:
    return CalendarInvalid(issues=(CalendarFieldIssue.at(root, error.path, CalendarIssueCode.INVALID_CALENDAR, str(error)),))


class CalendarValidator:
    @staticmethod
    def validate(request: ValidateCalendarInput) -> CalendarValidated | CalendarInvalid | CalendarBudgetExceeded:
        issues = ValidatorAggregationHelper((CalendarFieldIssue,))
        try:
            validated_indexes(request.settings, request.budget, issues)
        except ExhaustedBudget:
            return CalendarBudgetExceeded(budget=request.budget)
        except InvalidCalendar as error:
            return invalid(error)
        if facts := issues.snapshot():
            return CalendarInvalid(issues=facts)
        return CalendarValidated(settings=request.settings)
