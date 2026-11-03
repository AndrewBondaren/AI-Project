from app.application.time.calendar.projection import CalendarProjector
from app.application.time.calendar.validation import CalendarValidator
from app.application.time.changes.advancePipelineOpenPipeline import ITimeAdvancePipelineOpenPipeline, TimeAdvancePipelineOpenPipeline
from app.application.time.reads.reader import TimeReader
from app.application.time.reads.sourcePort import ITimeReadSource


def make_time_reader(source: ITimeReadSource) -> TimeReader:
    return TimeReader(source)


def make_time_advance_pipeline() -> ITimeAdvancePipelineOpenPipeline:
    return TimeAdvancePipelineOpenPipeline()


def make_calendar_projector() -> CalendarProjector:
    return CalendarProjector()


def make_calendar_validator() -> CalendarValidator:
    return CalendarValidator()
