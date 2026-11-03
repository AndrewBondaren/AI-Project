from typing import Annotated

from pydantic import Field

from app.dataModel.annotationPolicy import StrictOnWire
from app.dataModel.world.calendar.scalars import CalendarRecord, Nat
from app.dataModel.time.values.point import Nano


class CalendarClockTime(CalendarRecord):
    hour: StrictOnWire[Nat]
    minute: StrictOnWire[Annotated[int, Field(ge=0, le=59)]]
    second: StrictOnWire[Annotated[int, Field(ge=0, le=59)]]
    nanoseconds: StrictOnWire[Nano]
