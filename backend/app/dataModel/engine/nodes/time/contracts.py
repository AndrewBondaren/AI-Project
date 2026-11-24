"""Transport for Time section preparation."""

from app.dataModel.time.changes.section import PrepareTimeAdvanceSection, TimeAdvanceSection
from app.dataModel.time.results.section import TimeSectionContextMismatch
from app.dataModel.time.values.point import TimeRecord


class PrepareTimeSectionInput(TimeRecord):
    request: PrepareTimeAdvanceSection


class PrepareTimeSectionOutput(TimeRecord):
    value: TimeAdvanceSection | TimeSectionContextMismatch
