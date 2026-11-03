from bisect import bisect_right
from dataclasses import dataclass
from itertools import accumulate, chain, pairwise
from math import lcm

from app.dataModel.world.calendar.dates.date import CalendarDate
from app.dataModel.world.calendar.definitions.definition import CalendarDefinition
from app.dataModel.world.calendar.enums.rules import CalendarNumbering
from app.dataModel.world.calendar.rules.edits import CalendarSpan
from app.dataModel.world.calendar.rules.predicates import YearModuloPredicate, YearRangePredicate
from .rules import ExhaustedBudget, InvalidCalendar, Work, matches, year_shape


def _region_size(definition: CalendarDefinition, low: int | None, high: int | None, remaining: int) -> int:
    # Range predicates have constant truth between consecutive boundaries.
    sample = low if low is not None else (high - 1 if high is not None else 0)
    width = high - low if high is not None and low is not None else None
    period = 1
    for rule in definition.rules:
        condition = rule.condition
        if any(isinstance(p, YearRangePredicate) and not matches(p, sample) for p in condition.all_of):
            continue
        if any(isinstance(p, YearRangePredicate) and matches(p, sample) for p in condition.none_of):
            continue
        for predicate in chain(condition.all_of, condition.none_of):
            if isinstance(predicate, YearModuloPredicate):
                period = lcm(period, predicate.modulus)
                if width is not None and width <= period:
                    return width
                if period > remaining:
                    raise ExhaustedBudget
    return period


@dataclass
class Region:
    origin: int
    shapes: tuple[tuple[CalendarSpan, ...], ...]
    days: tuple[int, ...]
    week_days: tuple[int, ...]
    day_origin: int = 0
    week_origin: int = 0

    def count(self, year: int, prefix: tuple[int, ...]) -> int:
        cycles, offset = divmod(year - self.origin, len(self.shapes))
        return cycles * prefix[-1] + prefix[offset]


class CalendarIndex:
    """Year shapes repeat within each region of constant YEAR_RANGE truth.

    Prefixes count both physical days and days participating in the week.
    Each region is translated to the same day zero before binary lookup.
    """

    def __init__(self, definition: CalendarDefinition, work: Work):
        self.definition = definition
        boundaries: set[int] = set()
        for rule in definition.rules:
            for predicate in chain(rule.condition.all_of, rule.condition.none_of):
                if isinstance(predicate, YearRangePredicate):
                    boundaries.update((predicate.first, predicate.last + 1))
        self.starts = sorted(boundaries)
        self.regions: list[Region] = []
        for low, high in pairwise([None, *self.starts, None]):
            size = _region_size(definition, low, high, work.patterns)
            work.patterns -= size
            if work.patterns < 0:
                raise ExhaustedBudget
            origin = low if low is not None else 0
            if low is None and high is not None:
                origin = high - size
            shapes = tuple(year_shape(definition, y, work) for y in range(origin, origin + size))
            days = tuple(accumulate((sum(s.days for s in row) for row in shapes), initial=0))
            weeks = tuple(accumulate((sum(s.days for s in row if s.counts_in_week) for row in shapes), initial=0))
            self.regions.append(Region(origin, shapes, days, weeks))
        zero = bisect_right(self.starts, 0)
        reference = self.regions[zero]
        reference.day_origin = -reference.count(0, reference.days)
        reference.week_origin = -reference.count(0, reference.week_days)
        for i in range(zero + 1, len(self.regions)):
            a, b = self.regions[i-1:i+1]
            b.day_origin = a.day_origin + a.count(b.origin, a.days)
            b.week_origin = a.week_origin + a.count(b.origin, a.week_days)
        for i in reversed(range(zero)):
            a, b = self.regions[i:i+2]
            a.day_origin = b.day_origin - a.count(b.origin, a.days)
            a.week_origin = b.week_origin - a.count(b.origin, a.week_days)
        self.day_starts = [r.day_origin for r in self.regions[1:]]

    def astronomical(self, label: int) -> int:
        if self.definition.numbering == CalendarNumbering.NO_YEAR_ZERO:
            if label == 0:
                raise InvalidCalendar(("year",), "year zero is unavailable")
            return label + int(label < 0)
        return label

    def label(self, year: int) -> int:
        return year - int(year <= 0 and self.definition.numbering == CalendarNumbering.NO_YEAR_ZERO)

    def ordinal(self, date: CalendarDate) -> int:
        year = self.astronomical(date.year)
        region = self.regions[bisect_right(self.starts, year)]
        offset = region.day_origin + region.count(year, region.days)
        for span in region.shapes[(year - region.origin) % len(region.shapes)]:
            if span.span == date.span and date.day <= span.days:
                return offset + date.day - 1
            offset += span.days
        raise InvalidCalendar(("date",), "date outside year shape")

    def locate(self, ordinal: int) -> tuple[CalendarDate, CalendarSpan, int, int]:
        region = self.regions[bisect_right(self.day_starts, ordinal)]
        cycles, remainder = divmod(ordinal - region.day_origin, region.days[-1])
        i = bisect_right(region.days, remainder) - 1
        day = remainder - region.days[i]
        year = region.origin + cycles * len(region.shapes) + i
        within_week = 0
        for span in region.shapes[i]:
            if day < span.days:
                within_week += day if span.counts_in_week else 0
                total = region.week_origin + region.count(year, region.week_days) + within_week
                date = CalendarDate(year=self.label(year), span=span.span, day=day + 1)
                return date, span, within_week, total
            day -= span.days
            if span.counts_in_week:
                within_week += span.days
        raise AssertionError("year prefix disagrees with spans")
