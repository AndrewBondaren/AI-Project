from app.application.time.calendar.validation import CalendarValidator
from app.dataModel.world.calendar.projection.errors import CalendarBudgetExceeded
from app.dataModel.world.settings.timeOperations.results import PreparedTimeSettingsChange, SettingsInvalid
from .shared.candidate import issue, prepare
from app.dataModel.world.calendar.epochs.registry import WorldCalendarEpochRegistry
from app.dataModel.world.settings.timeOperations.changes import EpochCreate, EpochUpdate, EpochRemove


class WorldEpochSettingsPipelineOpenPipeline:
    def __init__(self, validator: CalendarValidator):
        self._validator = validator

    def prepare_epoch_create(self, request: EpochCreate) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded:
        settings = request.base.capture.settings
        entries = settings.epochs.entries
        key = request.epoch.system_epoch
        if any(e.system_epoch == key for e in entries):
            return issue("epoch", "epoch already exists")
        registry = WorldCalendarEpochRegistry(entries=(*entries, request.epoch))
        return prepare(request.base, settings.model_copy(update={"epochs": registry}), self._validator)

    def prepare_epoch_update(self, request: EpochUpdate) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded:
        settings = request.base.capture.settings
        entries = settings.epochs.entries
        key = request.epoch.system_epoch
        if not any(e.system_epoch == key for e in entries):
            return issue("epoch", "unknown epoch")
        registry = WorldCalendarEpochRegistry(entries=tuple(request.epoch if e.system_epoch == key else e for e in entries))
        return prepare(request.base, settings.model_copy(update={"epochs": registry}), self._validator)

    def prepare_epoch_remove(self, request: EpochRemove) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded:
        settings = request.base.capture.settings
        entries = settings.epochs.entries
        key = request.epoch
        if not any(e.system_epoch == key for e in entries):
            return issue("epoch", "unknown epoch")
        registry = WorldCalendarEpochRegistry(entries=tuple(e for e in entries if e.system_epoch != key))
        return prepare(request.base, settings.model_copy(update={"epochs": registry}), self._validator)
