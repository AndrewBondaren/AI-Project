from typing import Protocol, assert_never

from app.application.time.calendar.rules import Work
from app.dataModel.world.settings.timeOperations.batch import PrepareTimeSettingsBatch, SettingsBatchInputMismatch, SettingsBatchRefused
from app.dataModel.world.settings.timeOperations.changes import HoursChange, CalendarCreate, CalendarUpdate, CalendarSelect, CalendarRemove, EpochCreate, EpochUpdate, EpochRemove
from app.dataModel.world.settings.timeOperations.results import PreparedTimeSettingsChange
from .algorithms.hours import hours_change
from .algorithms.calendar import calendar_create, calendar_update, calendar_select, calendar_remove
from .algorithms.epoch import epoch_create, epoch_update, epoch_remove
from .shared.context import CandidatePreparation


class ITimeSettingsBatchPipelineOpenPipeline(Protocol):
    def prepare_batch(self, request: PrepareTimeSettingsBatch) -> PreparedTimeSettingsChange | SettingsBatchInputMismatch | SettingsBatchRefused: ...


class TimeSettingsBatchPipelineOpenPipeline:
    def prepare_batch(self, request: PrepareTimeSettingsBatch) -> PreparedTimeSettingsChange | SettingsBatchInputMismatch | SettingsBatchRefused:
        request = PrepareTimeSettingsBatch.model_validate(request, strict=True)
        base = request.commands[0].base
        indices = tuple(i for i, command in enumerate(request.commands) if command.base != base)
        if indices:
            return SettingsBatchInputMismatch(request=request, indices=indices)
        context = CandidatePreparation(base, base.capture.settings, work=Work.from_budget(base.budget))
        for index, command in enumerate(request.commands):
            match command:
                case HoursChange():
                    result = hours_change(command, context)
                case CalendarCreate():
                    result = calendar_create(command, context)
                case CalendarUpdate():
                    result = calendar_update(command, context)
                case CalendarSelect():
                    result = calendar_select(command, context)
                case CalendarRemove():
                    result = calendar_remove(command, context)
                case EpochCreate():
                    result = epoch_create(command, context)
                case EpochUpdate():
                    result = epoch_update(command, context)
                case EpochRemove():
                    result = epoch_remove(command, context)
                case _:
                    assert_never(command)
            if not isinstance(result, PreparedTimeSettingsChange):
                return SettingsBatchRefused(command_index=index, reason=result)
            context.settings = result.after
        return PreparedTimeSettingsChange(operation_id=base.operation_id, expected=base.capture.source,
            before=base.capture.settings, after=context.settings, effective_at=base.clock.point)
