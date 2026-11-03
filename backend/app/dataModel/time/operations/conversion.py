from app.dataModel.time.values.duration import U63
from app.dataModel.time.values.point import Nano, TimeRecord


class SecondsInput(TimeRecord):
    seconds: U63
    nanoseconds: Nano


class HoursInput(TimeRecord):
    hours: U63
