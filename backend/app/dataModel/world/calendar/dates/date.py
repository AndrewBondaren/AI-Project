from app.dataModel.annotationPolicy import StrictOnWire
from app.dataModel.world.calendar.scalars import CalendarRecord, Key, Pos
from app.dataModel.world.calendar.catalogs.spans import CalendarSpanRegistry


class CalendarDate(CalendarRecord):
    year: StrictOnWire[int]
    span: StrictOnWire[Key[CalendarSpanRegistry]]
    day: StrictOnWire[Pos]
