from app.dataModel.time.operations.arithmetic import PointResult
from app.dataModel.time.reads.capture import TimeCapture
from app.dataModel.time.values.point import MAX_SECONDS, NANOS_PER_SECOND, TimePoint
from app.dataModel.world.calendar.dates.clock import CalendarClockTime
from app.dataModel.world.calendar.definitions.definition import CalendarEntry
from app.dataModel.world.calendar.enums.rules import CalendarConversionKind, CalendarWeekMode
from app.dataModel.world.calendar.projection.errors import (
    CalendarBudgetExceeded, CalendarInvalid, CalendarScopeMismatch, CalendarSourceMismatch, CalendarTimeOverflow,
)
from app.dataModel.world.calendar.projection.request import CalendarProjectionInput, CalendarResolveInput
from app.dataModel.world.calendar.projection.result import CalendarProjection
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.world.settings.timeSettings import WorldTimeSettings
from .ordinal import CalendarIndex
from .rules import ExhaustedBudget, InvalidCalendar
from .validation import invalid, validated_indexes


def clock_nanos(time: CalendarClockTime) -> int:
    return ((time.hour * 60 + time.minute) * 60 + time.second) * NANOS_PER_SECOND + time.nanoseconds


def origin_offset(entry: CalendarEntry, index: CalendarIndex, day_length: int) -> int:
    anchor = entry.anchor
    coordinate = anchor.coordinate_seconds * NANOS_PER_SECOND + anchor.coordinate_nanoseconds
    return index.ordinal(anchor.origin.date) * day_length + clock_nanos(anchor.origin.time) - coordinate


def entry_for(request: CalendarProjectionInput | CalendarResolveInput) -> CalendarEntry:
    resolved = request.resolved
    if request.calendar != resolved.version.calendar_key:
        raise InvalidCalendar(("resolved", "version"), "calendar differs from pinned version")
    entry = resolved.settings.calendars.entry_for(request.calendar)
    if entry is None:
        raise InvalidCalendar(("calendar",), "unknown calendar")
    return entry


class CalendarProjector:
    @staticmethod
    def project(request: CalendarProjectionInput) -> CalendarProjection | CalendarSourceMismatch | CalendarScopeMismatch | CalendarInvalid | CalendarBudgetExceeded | CalendarTimeOverflow:
        capture = request.capture
        expected = capture.publication if isinstance(capture, TimeCapture) else capture.snapshot
        resolved = request.resolved
        if resolved.source != expected or resolved.version.publication.world_uid != expected.world_uid:
            actual = resolved.source if resolved.source != expected else resolved.version.publication
            return CalendarSourceMismatch(expected=expected, actual=actual)
        if request.point.scope != capture.point.scope:
            return CalendarScopeMismatch(expected=capture.point.scope, actual=request.point.scope)
        try:
            entry = entry_for(request)
            index = validated_indexes(resolved.settings, request.budget)[request.calendar]
        except ExhaustedBudget:
            return CalendarBudgetExceeded(budget=request.budget)
        except InvalidCalendar as error:
            return invalid(error, WorldTimeSettings if error.path[0] in ("selected", "calendars", "epochs") else type(request))
        definition = entry.definition
        day_length = resolved.settings.hours_per_day * 3600 * NANOS_PER_SECOND
        offset = origin_offset(entry, index, day_length)
        point = request.point
        ordinal, remainder = divmod(point.seconds * NANOS_PER_SECOND + point.nanoseconds + offset, day_length)
        date, span, within_week, total = index.locate(ordinal)
        seconds, nanos = divmod(remainder, NANOS_PER_SECOND)
        hour, seconds = divmod(seconds, 3600)
        minute, second = divmod(seconds, 60)
        time = CalendarClockTime(hour=hour, minute=minute, second=second, nanoseconds=nanos)
        weekday = None
        weekdays = definition.weekdays.entries
        if weekdays and span.counts_in_week:
            shift = within_week
            if definition.week_mode == CalendarWeekMode.CONTINUOUS:
                shift = total - index.locate(definition.week_anchor_ordinal)[3]
            weekday = weekdays[(definition.week_anchor_index + shift) % len(weekdays)].system_weekday
        period = max((p for p in definition.periods.entries if p.start <= (hour, minute)), key=lambda p: p.start)
        epochs = (e for e in resolved.settings.epochs.entries if e.calendar == request.calendar
                  and (e.start_seconds, e.start_nanoseconds) <= point.coordinate)
        epoch = max(epochs, key=lambda e: (e.start_seconds, e.start_nanoseconds), default=None)
        epoch_year = None
        if epoch is not None:
            start = (epoch.start_seconds * NANOS_PER_SECOND + epoch.start_nanoseconds + offset) // day_length
            years = index.astronomical(date.year) - index.astronomical(index.locate(start)[0].year)
            epoch_year = index.label(index.astronomical(epoch.start_year_label) + years)
        return CalendarProjection(point=point, version=resolved.version, date=date, time=time, weekday=weekday,
                                  season=span.season, period=period.system_period,
                                  epoch=epoch.system_epoch if epoch else None, epoch_year=epoch_year)

    @staticmethod
    def resolve(request: CalendarResolveInput) -> PointResult | CalendarSourceMismatch | CalendarInvalid | CalendarBudgetExceeded | CalendarTimeOverflow:
        source = request.resolved.source
        if source.world_uid != request.resolved.version.publication.world_uid:
            return CalendarSourceMismatch(expected=source, actual=request.resolved.version.publication)
        timeline = source.active_timeline_id if isinstance(source, WorldPublicationRef) else source.timeline_id
        try:
            if source.world_uid != request.scope.world_uid or timeline != request.scope.timeline_id:
                raise InvalidCalendar(("scope",), "scope differs from calendar source")
            entry = entry_for(request)
            settings = request.resolved.settings
            index = validated_indexes(settings, request.budget)[request.calendar]
            if request.time.hour >= settings.hours_per_day:
                raise InvalidCalendar(("time", "hour"), "hour outside day")
            day_length = settings.hours_per_day * 3600 * NANOS_PER_SECOND
            try:
                ordinal = index.ordinal(request.date)
            except InvalidCalendar as error:
                path = ("date", "year") if error.path == ("year",) else ("date",)
                raise InvalidCalendar(path, str(error)) from error
            total = ordinal * day_length + clock_nanos(request.time)
            seconds, nanos = divmod(total - origin_offset(entry, index, day_length), NANOS_PER_SECOND)
        except ExhaustedBudget:
            return CalendarBudgetExceeded(budget=request.budget)
        except InvalidCalendar as error:
            return invalid(error, WorldTimeSettings if error.path[0] in ("selected", "calendars", "epochs") else type(request))
        if not -MAX_SECONDS-1 <= seconds <= MAX_SECONDS:
            return CalendarTimeOverflow(operation=CalendarConversionKind.RESOLVE)
        return PointResult(point=TimePoint(world_uid=source.world_uid, timeline_id=request.scope.timeline_id,
                                           seconds=seconds, nanoseconds=nanos))
