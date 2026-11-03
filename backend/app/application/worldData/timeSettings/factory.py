from app.application.time.calendar.projection import CalendarProjector
from app.application.time.calendar.validation import CalendarValidator
from .reader import WorldTimeSettingsReader
from .sourcePort import IWorldTimeSettingsSource
from .preparation.calendarPipelineOpenPipeline import WorldCalendarSettingsPipelineOpenPipeline
from .preparation.initialPipelineOpenPipeline import WorldInitialTimeSettingsPipelineOpenPipeline
from .preparation.epochPipelineOpenPipeline import WorldEpochSettingsPipelineOpenPipeline
from .preparation.hoursPipelineOpenPipeline import WorldHoursSettingsPipelineOpenPipeline


def make_world_settings_reader(source: IWorldTimeSettingsSource) -> WorldTimeSettingsReader:
    return WorldTimeSettingsReader(source)


def make_calendar_settings_pipeline(validator: CalendarValidator, projector: CalendarProjector) -> WorldCalendarSettingsPipelineOpenPipeline:
    return WorldCalendarSettingsPipelineOpenPipeline(validator, projector)


def make_epoch_settings_pipeline(validator: CalendarValidator) -> WorldEpochSettingsPipelineOpenPipeline:
    return WorldEpochSettingsPipelineOpenPipeline(validator)


def make_hours_settings_pipeline(validator: CalendarValidator, projector: CalendarProjector) -> WorldHoursSettingsPipelineOpenPipeline:
    return WorldHoursSettingsPipelineOpenPipeline(validator, projector)


def make_initial_settings_pipeline(validator: CalendarValidator) -> WorldInitialTimeSettingsPipelineOpenPipeline:
    return WorldInitialTimeSettingsPipelineOpenPipeline(validator)
