from app.dataModel.annotationPolicy import StrictOnWire
from app.dataModel.world.calendar.scalars import CalendarRecord
from app.dataModel.time.values.point import I64, Nano
from .date import CalendarDate
from .clock import CalendarClockTime


class CalendarOrigin(CalendarRecord):
    date: StrictOnWire[CalendarDate]
    time: StrictOnWire[CalendarClockTime]


class CalendarAnchor(CalendarRecord):
    coordinate_seconds: StrictOnWire[I64]
    coordinate_nanoseconds: StrictOnWire[Nano]
    origin: StrictOnWire[CalendarOrigin]
