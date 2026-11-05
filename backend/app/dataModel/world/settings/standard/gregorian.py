"""World-owned canonical calendar data for STANDARD initialization."""

from datetime import datetime

from app.dataModel.registryKey import RegistryKey
from app.dataModel.world.calendar.catalogs.periods import CalendarPeriodRegistry, PeriodEntry
from app.dataModel.world.calendar.catalogs.seasons import CalendarSeasonRegistry, SeasonEntry
from app.dataModel.world.calendar.catalogs.spans import CalendarSpanRegistry, SpanEntry
from app.dataModel.world.calendar.catalogs.weekdays import CalendarWeekdayRegistry, WeekdayEntry
from app.dataModel.world.calendar.dates.anchor import CalendarAnchor, CalendarOrigin
from app.dataModel.world.calendar.dates.clock import CalendarClockTime
from app.dataModel.world.calendar.dates.date import CalendarDate
from app.dataModel.world.calendar.definitions.definition import CalendarDefinition, CalendarEntry
from app.dataModel.world.calendar.definitions.registry import WorldCalendarRegistry
from app.dataModel.world.calendar.enums.rules import (
    CalendarEditKind, CalendarNumbering, CalendarPredicateKind, CalendarSpanRole, CalendarWeekMode,
)
from app.dataModel.world.calendar.rules.edits import CalendarSpan, ReplaceSpanRule
from app.dataModel.world.calendar.rules.predicates import CalendarCondition, YearModuloPredicate


_MONTHS = (
    ("january", "Январь", 31, "winter"), ("february", "Февраль", 28, "winter"),
    ("march", "Март", 31, "spring"), ("april", "Апрель", 30, "spring"),
    ("may", "Май", 31, "spring"), ("june", "Июнь", 30, "summer"),
    ("july", "Июль", 31, "summer"), ("august", "Август", 31, "summer"),
    ("september", "Сентябрь", 30, "autumn"), ("october", "Октябрь", 31, "autumn"),
    ("november", "Ноябрь", 30, "autumn"), ("december", "Декабрь", 31, "winter"),
)
_WEEKDAYS = (
    ("monday", "Понедельник"), ("tuesday", "Вторник"), ("wednesday", "Среда"),
    ("thursday", "Четверг"), ("friday", "Пятница"), ("saturday", "Суббота"), ("sunday", "Воскресенье"),
)
_SEASONS = (("winter","Зима"), ("spring","Весна"), ("summer","Лето"), ("autumn","Осень"))
_PERIODS = (("night","Ночь"), ("morning","Утро"), ("day","День"), ("evening","Вечер"))
_SHORT_PERIODS = {
    1: (("morning", 0, 0), ("day", 0, 20), ("night", 0, 40)),
    2: (("day", 0, 0), ("night", 1, 0)),
    3: (("morning", 0, 0), ("day", 1, 0), ("night", 2, 0)),
}


def _standard_periods(hours: int) -> CalendarPeriodRegistry:
    starts = _SHORT_PERIODS.get(hours)
    if starts is None:
        starts = tuple((key, (i * hours + 3) // 4, 0) for i, (key, _) in enumerate(_PERIODS))
    labels = dict(_PERIODS)
    return CalendarPeriodRegistry(entries=tuple(
        PeriodEntry(system_period=RegistryKey(key), display_period=labels[key], from_hour=hour, from_minute=minute)
        for key, hour, minute in starts))


def origin_from_utc(instant: datetime) -> CalendarOrigin:
    return CalendarOrigin(
        date=CalendarDate(year=instant.year, span=RegistryKey(_MONTHS[instant.month-1][0]), day=instant.day),
        time=CalendarClockTime(hour=instant.hour, minute=instant.minute, second=instant.second,
                               nanoseconds=instant.microsecond * 1000),
    )


def _multiple_of(modulus: int) -> YearModuloPredicate:
    return YearModuloPredicate(kind=CalendarPredicateKind.YEAR_MODULO, modulus=modulus, residue=0, offset=0)


def standard_entry(hours: int, origin: CalendarOrigin) -> CalendarEntry:
    base = tuple(CalendarSpan(span=RegistryKey(key), days=days, counts_in_week=True, season=RegistryKey(season))
                 for key, _, days, season in _MONTHS)
    leap = base[1].model_copy(update={"days":29})
    key: RegistryKey[WorldCalendarRegistry] = RegistryKey("gregorian")
    definition = CalendarDefinition(
        system_calendar=key, display_calendar="Григорианский", description="",
        numbering=CalendarNumbering.NO_YEAR_ZERO, week_mode=CalendarWeekMode.CONTINUOUS,
        week_anchor_ordinal=719528, week_anchor_index=3,  # 1970-01-01, Thursday
        spans=CalendarSpanRegistry(entries=tuple(
            SpanEntry(system_span=RegistryKey(name), display_span=label, role=CalendarSpanRole.MONTH)
            for name, label, _, _ in _MONTHS)),
        weekdays=CalendarWeekdayRegistry(entries=tuple(
            WeekdayEntry(system_weekday=RegistryKey(name), display_weekday=label) for name, label in _WEEKDAYS)),
        seasons=CalendarSeasonRegistry(entries=tuple(
            SeasonEntry(system_season=RegistryKey(name), display_season=label) for name, label in _SEASONS)),
        periods=_standard_periods(hours),
        base_year=base,
        rules=(
            ReplaceSpanRule(kind=CalendarEditKind.REPLACE_SPAN, value=leap, condition=CalendarCondition(
                all_of=(_multiple_of(4),), none_of=(_multiple_of(100),))),
            ReplaceSpanRule(kind=CalendarEditKind.REPLACE_SPAN, value=leap, condition=CalendarCondition(
                all_of=(_multiple_of(400),), none_of=())),
        ),
    )
    return CalendarEntry(definition=definition, anchor=CalendarAnchor(
        coordinate_seconds=0, coordinate_nanoseconds=0, origin=origin))
